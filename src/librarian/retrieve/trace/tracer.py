"""Every ask leaves a trace: each step it went through, in order, with its time.

The pipeline calls `trace` and nothing else. Events wait in memory and go to the store in
batches: on a timer, at once when a run ends (`finished` or `failed`), and at process exit,
so only a hard kill loses the tail. Events follow the shape of OpenTelemetry's GenAI
conventions where one fits: the correlation id is the trace, a step is a span.

Two stores behind one interface, picked by LIBRARIAN_TRACE_STORE: files (one .jsonl per
run under TRACES_DIR) and Postgres (`asks` and `ask_events`, as the app's login).

Tracing never breaks an ask: a batch the store refuses goes back in front of what's waiting
and the next flush tries it again, its error printed to stderr, never raised.
"""

import atexit
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy import select

from librarian.config import TRACE_STORE, TRACES_DIR
from librarian.db import Session
from librarian.models import Ask, AskEvent, AskStatus

FLUSH_SECONDS = 5
ENDS = ("finished", "failed")


class Event(BaseModel):
    """One thing a run did. The pipeline says step, kind and data, with `round` on round
    events and `ms` on the event that ends a step; `trace` sets seq and at."""

    seq: int = 0
    at: datetime | None = None
    step: str
    round: int | None = None
    kind: str
    ms: int | None = None
    data: dict[str, Any]


class Store(Protocol):
    def write(self, correlation_id: str, events: list[Event]) -> None: ...

    def read(self, correlation_id: str) -> list[Event]: ...


class FileStore:
    """<directory>/<correlation id>.jsonl, one event per line."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, correlation_id: str, events: list[Event]) -> None:
        """All of the batch or none of it: a write cut short (disk full) is truncated
        away, so the retry doesn't repeat lines."""
        text = ""
        for event in events:
            text += event.model_dump_json() + "\n"
        data = text.encode("utf-8")
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._path(correlation_id).open("ab", buffering=0) as file:
            start = file.tell()
            try:
                written = file.write(data)
                if written != len(data):
                    raise OSError(f"wrote {written} of {len(data)} bytes")
            except OSError:
                file.truncate(start)
                raise

    def read(self, correlation_id: str) -> list[Event]:
        path = self._path(correlation_id)
        events: list[Event] = []
        if not path.exists():
            return events
        for line in path.read_text(encoding="utf-8").splitlines():
            events.append(Event.model_validate_json(line))
        return events

    def _path(self, correlation_id: str) -> Path:
        return self.directory / f"{correlation_id}.jsonl"


class PostgresStore:
    """The run's `asks` row, created by `started` and completed by `finished` or `failed`,
    and its events in `ask_events`, in one transaction: an event never exists without its run."""

    def write(self, correlation_id: str, events: list[Event]) -> None:
        with Session() as session:
            run = session.get(Ask, correlation_id)
            for event in events:
                data = event.model_dump(mode="json")["data"]
                if event.step == "started":
                    run = Ask(
                        correlation_id=correlation_id,
                        started_at=event.at,
                        question=data["question"],
                        agent_model=data["agent_model"],
                        refine_model=data["refine_model"],
                        reasoning=data["reasoning"],
                        prompt=data["prompt"],
                        git_sha=data["git_sha"],
                    )
                    session.add(run)
                elif event.step in ENDS:
                    if run is None:
                        raise RuntimeError(f"no asks row for {correlation_id}")
                    run.finished_at = event.at
                    if event.step == "failed":
                        run.status = AskStatus.error
                        run.error = data["error"]
                    elif data["status"] is not None:
                        run.status = AskStatus(data["status"])
                    run.tokens_in = data["input_tokens"]
                    run.tokens_out = data["output_tokens"]
                    run.rounds = data["rounds"]
                    run.calls = data["calls"]
                    run.ms = event.ms
                session.add(
                    AskEvent(
                        correlation_id=correlation_id,
                        seq=event.seq,
                        at=event.at,
                        step=event.step,
                        round=event.round,
                        kind=event.kind,
                        ms=event.ms,
                        data=data,
                    )
                )
            session.commit()

    def read(self, correlation_id: str) -> list[Event]:
        query = (
            select(AskEvent).where(AskEvent.correlation_id == correlation_id).order_by(AskEvent.seq)
        )
        events: list[Event] = []
        with Session() as session:
            for row in session.scalars(query):
                events.append(
                    Event(
                        seq=row.seq,
                        at=row.at,
                        step=row.step,
                        round=row.round,
                        kind=row.kind,
                        ms=row.ms,
                        data=row.data,
                    )
                )
        return events


store: Store = FileStore(TRACES_DIR)
if TRACE_STORE == "postgres":
    store = PostgresStore()
elif TRACE_STORE != "file":
    raise ValueError(f"LIBRARIAN_TRACE_STORE is {TRACE_STORE!r}, not file or postgres")

# _pending and _next_seq under _lock; _writing keeps flushes in order, one at a time.
_lock = threading.Lock()
_writing = threading.Lock()
_pending: dict[str, list[Event]] = {}
_next_seq: dict[str, int] = {}
_timer: threading.Timer | None = None


def trace(correlation_id: str, event: Event) -> None:
    with _lock:
        event.seq = _next_seq.get(correlation_id, 0)
        event.at = datetime.now(UTC)
        _next_seq[correlation_id] = event.seq + 1
        if event.step in ENDS:
            del _next_seq[correlation_id]
        if correlation_id not in _pending:
            _pending[correlation_id] = []
        _pending[correlation_id].append(event)
        _arm()
    if event.step in ENDS:
        flush()


def flush() -> None:
    """Every waiting event to the store; what it refuses waits for the next flush."""
    global _pending, _timer
    with _writing:
        with _lock:
            batches = _pending
            _pending = {}
            if _timer is not None:
                _timer.cancel()
                _timer = None
        refused: dict[str, list[Event]] = {}
        for correlation_id, events in batches.items():
            try:
                store.write(correlation_id, events)
            except Exception as error:  # noqa: BLE001 - printed and retried, never the run's
                print(f"trace {correlation_id}: not written, retried: {error}", file=sys.stderr)
                refused[correlation_id] = events
        if not refused:
            return
        with _lock:
            for correlation_id, events in _pending.items():
                if correlation_id in refused:
                    refused[correlation_id].extend(events)
                else:
                    refused[correlation_id] = events
            _pending = refused
            _arm()


def _arm() -> None:
    """Start the timer, unless it is already running. Called under _lock."""
    global _timer
    if _timer is None:
        _timer = threading.Timer(FLUSH_SECONDS, flush)
        _timer.daemon = True
        _timer.start()


def _last_flush() -> None:
    flush()
    for correlation_id, events in _pending.items():
        print(f"trace {correlation_id}: {len(events)} events lost", file=sys.stderr)


atexit.register(_last_flush)
