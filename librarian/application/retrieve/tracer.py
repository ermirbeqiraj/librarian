"""Every ask leaves a trace: each step it went through, in order, with its time.

The ask calls `trace` and nothing else. Events wait in memory and go to the store in
batches: on a timer, at once when a run ends (`finished` or `failed`), and at process exit,
so only a hard kill loses the tail. Events follow the shape of OpenTelemetry's GenAI
conventions where one fits: the correlation id is the trace, a step is a span.

Tracing never breaks an ask: a batch the store refuses goes back in front of what's waiting
and the next flush tries it again, its error printed to stderr, never raised.
"""

import atexit
import sys
import threading
from datetime import UTC, datetime

from librarian.application.retrieve.ports import Event, TraceStore

FLUSH_SECONDS = 5
ENDS = ("finished", "failed")


class Tracer:
    def __init__(self, store: TraceStore) -> None:
        self.store = store
        self.flush_seconds = FLUSH_SECONDS
        # _pending and _next_seq under _lock; _writing keeps flushes in order, one at a time.
        self._lock = threading.Lock()
        self._writing = threading.Lock()
        self._pending: dict[str, list[Event]] = {}
        self._next_seq: dict[str, int] = {}
        self._timer: threading.Timer | None = None
        atexit.register(self._last_flush)

    def trace(self, correlation_id: str, event: Event) -> None:
        with self._lock:
            event.seq = self._next_seq.get(correlation_id, 0)
            event.at = datetime.now(UTC)
            self._next_seq[correlation_id] = event.seq + 1
            if event.step in ENDS:
                del self._next_seq[correlation_id]
            if correlation_id not in self._pending:
                self._pending[correlation_id] = []
            self._pending[correlation_id].append(event)
            self._arm()
        if event.step in ENDS:
            self.flush()

    def flush(self) -> None:
        """Every waiting event to the store; what it refuses waits for the next flush."""
        with self._writing:
            with self._lock:
                batches = self._pending
                self._pending = {}
                if self._timer is not None:
                    self._timer.cancel()
                    self._timer = None
            refused: dict[str, list[Event]] = {}
            for correlation_id, events in batches.items():
                try:
                    self.store.write(correlation_id, events)
                except Exception as error:  # noqa: BLE001 - printed and retried, never the run's
                    print(f"trace {correlation_id}: not written, retried: {error}", file=sys.stderr)
                    refused[correlation_id] = events
            if not refused:
                return
            with self._lock:
                for correlation_id, events in self._pending.items():
                    if correlation_id in refused:
                        refused[correlation_id].extend(events)
                    else:
                        refused[correlation_id] = events
                self._pending = refused
                self._arm()

    def _arm(self) -> None:
        """Start the timer, unless it is already running. Called under _lock."""
        if self._timer is None:
            self._timer = threading.Timer(self.flush_seconds, self.flush)
            self._timer.daemon = True
            self._timer.start()

    def _last_flush(self) -> None:
        self.flush()
        for correlation_id, events in self._pending.items():
            print(f"trace {correlation_id}: {len(events)} events lost", file=sys.stderr)
