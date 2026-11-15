"""The tracer and its two stores. Each test runs once with files and once with the test
database, except two: the cut-short write needs files only, the reader-role test the
database only."""

import resource
import signal
import time
from pathlib import Path

import pytest
from conftest import RefusingStore

from librarian.retrieve.sql import run_sql
from librarian.retrieve.trace import tracer
from librarian.retrieve.trace.tracer import Event, FileStore, Store, trace

TOTALS = {"input_tokens": 0, "output_tokens": 0, "rounds": 0, "calls": 0}


def started() -> Event:
    data = {
        "question": "q",
        "agent_model": "fake",
        "refine_model": "fake",
        "reasoning": "high",
        "prompt": "dig.md",
        "git_sha": None,
    }
    return Event(step="started", kind="started", data=data)


def test_a_run_waits_in_memory_until_it_finishes(trace_store: Store) -> None:
    trace("run-1", started())
    trace("run-1", Event(step="case", kind="case", data={"message": "q"}))
    assert trace_store.read("run-1") == []
    finished = dict(TOTALS)
    finished["status"] = "found"
    trace("run-1", Event(step="finished", kind="finished", ms=5, data=finished))
    events = trace_store.read("run-1")
    names: list[str] = []
    for event in events:
        names.append(f"{event.seq} {event.step}")
    assert names == ["0 started", "1 case", "2 finished"]


def test_a_failed_run_is_flushed_at_once(trace_store: Store) -> None:
    trace("run-2", started())
    failed = dict(TOTALS)
    failed["error"] = "boom"
    failed["step"] = "refine"
    trace("run-2", Event(step="failed", kind="failed", ms=5, data=failed))
    assert trace_store.read("run-2")[-1].data["error"] == "boom"


def test_the_timer_flushes_a_run_that_has_not_ended(
    trace_store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracer, "FLUSH_SECONDS", 0.05)
    trace("run-3", started())
    deadline = time.monotonic() + 5
    while trace_store.read("run-3") == [] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(trace_store.read("run-3")) == 1
    trace("run-3", Event(step="case", kind="case", data={"message": "q"}))
    deadline = time.monotonic() + 5
    while len(trace_store.read("run-3")) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert trace_store.read("run-3")[1].seq == 1


def test_a_refused_batch_waits_and_the_next_flush_writes_it(
    trace_store: Store, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(tracer, "store", RefusingStore(trace_store, times=1))
    trace("run-4", started())
    finished = dict(TOTALS)
    finished["status"] = "found"
    trace("run-4", Event(step="finished", kind="finished", ms=5, data=finished))
    assert "trace run-4: not written, retried: No space left on device" in capsys.readouterr().err
    assert trace_store.read("run-4") == []
    trace("run-5", started())
    tracer.flush()
    seqs: list[int] = []
    for event in trace_store.read("run-4"):
        seqs.append(event.seq)
    assert seqs == [0, 1]
    assert len(trace_store.read("run-5")) == 1


def test_what_the_store_still_refuses_at_exit_is_reported_lost(
    trace_store: Store, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(tracer, "store", RefusingStore(trace_store, times=99))
    trace("run-6", started())
    trace("run-6", Event(step="case", kind="case", data={"message": "q"}))
    tracer._last_flush()
    assert "trace run-6: 2 events lost" in capsys.readouterr().err
    monkeypatch.setattr(tracer, "store", trace_store)


def test_a_file_write_cut_short_leaves_nothing_to_repeat(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    store.write("run-7", [started()])
    path = tmp_path / "run-7.jsonl"
    size = path.stat().st_size
    system = Event(step="system", kind="system", data={"text": "x" * 10_000})
    # Past the file size limit the kernel writes short; ignored, SIGXFSZ won't kill pytest.
    handler = signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (size + 100, hard))
    try:
        with pytest.raises(OSError):
            store.write("run-7", [system])
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
        signal.signal(signal.SIGXFSZ, handler)
    assert path.stat().st_size == size
    assert len(store.read("run-7")) == 1


@pytest.mark.parametrize("table", ["asks", "ask_events", "ask_feedback"])
def test_the_reader_cannot_read_past_questions(test_db: None, table: str) -> None:
    result = run_sql(f"SELECT * FROM {table}")
    assert result.error is not None
    assert "permission denied" in result.error
