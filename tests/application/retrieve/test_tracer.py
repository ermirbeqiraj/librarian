"""The tracer, once with each store: files, then the test database."""

import time

import pytest
from conftest import RefusingStore

from librarian.application.retrieve.ports import Event, TraceStore
from librarian.application.retrieve.tracer import Tracer

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


def test_a_run_waits_in_memory_until_it_finishes(tracer: Tracer, trace_store: TraceStore) -> None:
    tracer.trace("run-1", started())
    tracer.trace("run-1", Event(step="case", kind="case", data={"message": "q"}))
    assert trace_store.read("run-1") == []
    finished = dict(TOTALS)
    finished["status"] = "found"
    tracer.trace("run-1", Event(step="finished", kind="finished", ms=5, data=finished))
    events = trace_store.read("run-1")
    names: list[str] = []
    for event in events:
        names.append(f"{event.seq} {event.step}")
    assert names == ["0 started", "1 case", "2 finished"]


def test_a_failed_run_is_flushed_at_once(tracer: Tracer, trace_store: TraceStore) -> None:
    tracer.trace("run-2", started())
    failed = dict(TOTALS)
    failed["error"] = "boom"
    failed["step"] = "refine"
    tracer.trace("run-2", Event(step="failed", kind="failed", ms=5, data=failed))
    assert trace_store.read("run-2")[-1].data["error"] == "boom"


def test_the_timer_flushes_a_run_that_has_not_ended(
    tracer: Tracer, trace_store: TraceStore
) -> None:
    tracer.flush_seconds = 0.05
    tracer.trace("run-3", started())
    deadline = time.monotonic() + 5
    while trace_store.read("run-3") == [] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(trace_store.read("run-3")) == 1
    tracer.trace("run-3", Event(step="case", kind="case", data={"message": "q"}))
    deadline = time.monotonic() + 5
    while len(trace_store.read("run-3")) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert trace_store.read("run-3")[1].seq == 1


def test_a_refused_batch_waits_and_the_next_flush_writes_it(
    tracer: Tracer, trace_store: TraceStore, capsys: pytest.CaptureFixture[str]
) -> None:
    tracer.store = RefusingStore(trace_store, times=1)
    tracer.trace("run-4", started())
    finished = dict(TOTALS)
    finished["status"] = "found"
    tracer.trace("run-4", Event(step="finished", kind="finished", ms=5, data=finished))
    assert "trace run-4: not written, retried: No space left on device" in capsys.readouterr().err
    assert trace_store.read("run-4") == []
    tracer.trace("run-5", started())
    tracer.flush()
    seqs: list[int] = []
    for event in trace_store.read("run-4"):
        seqs.append(event.seq)
    assert seqs == [0, 1]
    assert len(trace_store.read("run-5")) == 1


def test_what_the_store_still_refuses_at_exit_is_reported_lost(
    tracer: Tracer, trace_store: TraceStore, capsys: pytest.CaptureFixture[str]
) -> None:
    tracer.store = RefusingStore(trace_store, times=99)
    tracer.trace("run-6", started())
    tracer.trace("run-6", Event(step="case", kind="case", data={"message": "q"}))
    tracer._last_flush()
    assert "trace run-6: 2 events lost" in capsys.readouterr().err
    tracer.store = trace_store
