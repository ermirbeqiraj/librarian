import pytest
from conftest import SESSIONS, RefusingStore
from fakes import SEARCH, SUBMIT, NoDocuments, Recorder, asker
from sqlalchemy import select

from librarian.adapters.postgres.models import Ask, AskStatus
from librarian.adapters.postgres.trace_store import PostgresStore
from librarian.application.retrieve import agent
from librarian.application.retrieve.ports import Event, TraceStore
from librarian.application.retrieve.result import Inquiry, LinkedSource, Result, Status, Value
from librarian.application.retrieve.tracer import Tracer


def steps(events: list[Event]) -> list[str]:
    names: list[str] = []
    for event in events:
        if event.round is None:
            names.append(event.step)
        else:
            names.append(f"{event.round} {event.kind}")
    return names


def asks_row(store: TraceStore) -> Ask | None:
    """The run's asks row when the store is Postgres, None for files."""
    if not isinstance(store, PostgresStore):
        return None
    with SESSIONS() as session:
        return session.scalars(select(Ask)).one()


def test_a_run_that_submits_leaves_every_event_in_order(
    tracer: Tracer, trace_store: TraceStore
) -> None:
    inquiry = asker(tracer, [SEARCH, SUBMIT]).ask("qnd scade la bolletta", "test-submits")
    assert inquiry.result is not None
    assert inquiry.result.trace_id == "test-submits"
    assert (inquiry.rounds, inquiry.calls, inquiry.tokens_in, inquiry.tokens_out) == (2, 2, 20, 4)
    events = trace_store.read("test-submits")
    assert steps(events) == [
        "started",
        "refine",
        "system",
        "case",
        "1 thinking",
        "1 usage",
        "1 tool_call",
        "1 tool_result",
        "2 thinking",
        "2 usage",
        "2 tool_call",
        "2 tool_result",
        "submitted",
        "verified",
        "linked",
        "finished",
    ]
    seqs: list[int] = []
    for event in events:
        seqs.append(event.seq)
    assert seqs == list(range(len(events)))
    assert events[0].data["question"] == "qnd scade la bolletta"
    assert events[1].data["output"] == [{"text": "bolletta corretta", "period": None}]
    assert events[1].data["input_tokens"] == 10
    assert events[6].data["arguments"] == {"query": "bolletta"}
    assert events[-1].data["status"] == "not_found"
    assert events[-1].ms is not None
    run = asks_row(trace_store)
    if run is not None:
        assert run.status == AskStatus.not_found
        assert run.finished_at is not None
        assert (run.rounds, run.calls, run.tokens_in) == (2, 2, 20)


def test_a_run_whose_model_raises_ends_failed_and_the_error_still_reaches_the_caller(
    tracer: Tracer, trace_store: TraceStore
) -> None:
    failing = asker(tracer, [SEARCH, RuntimeError("429 Too Many Requests")])
    with pytest.raises(RuntimeError, match="429"):
        failing.ask("qnd scade la bolletta", "test-fails")
    events = trace_store.read("test-fails")
    failed = events[-1]
    assert failed.step == "failed"
    assert failed.data["error"] == "RuntimeError: 429 Too Many Requests"
    assert failed.data["step"] == "round"
    assert failed.data["round"] == 2
    run = asks_row(trace_store)
    if run is not None:
        assert run.status == AskStatus.error
        assert run.error == "RuntimeError: 429 Too Many Requests"
        assert run.finished_at is not None


def test_a_store_that_is_down_never_breaks_the_ask(tracer: Tracer, trace_store: TraceStore) -> None:
    tracer.store = RefusingStore(trace_store, times=99)
    inquiry = asker(tracer, [SUBMIT]).ask("q", "test-store-down")
    assert inquiry.result is not None
    with pytest.raises(RuntimeError, match="429"):
        asker(tracer, [RuntimeError("429 Too Many Requests")]).ask("q", "test-store-down-fails")
    tracer.store = trace_store
    tracer.flush()
    assert trace_store.read("test-store-down")[-1].step == "finished"
    assert trace_store.read("test-store-down-fails")[-1].step == "failed"


def test_a_tool_error_lands_in_its_tool_result_and_the_run_goes_on(
    tracer: Tracer, trace_store: TraceStore
) -> None:
    script = [
        {"name": "sql", "args": {"query": "boom"}},
        {"name": "search", "args": {}},
        {"name": "nope", "args": {}},
        SUBMIT,
    ]
    asker(tracer, script).ask("q", "test-tool-error")
    errors: list[str | None] = []
    for event in trace_store.read("test-tool-error"):
        if event.kind == "tool_result":
            errors.append(event.data["error"])
    assert errors[0] == 'syntax error at or near "boom"'
    assert errors[1] is not None and "query" in errors[1]
    assert errors[2] is not None and "non esiste" in errors[2]
    assert errors[3] is None
    assert trace_store.read("test-tool-error")[-1].step == "finished"


def test_dig_stops_at_the_cap_after_the_nudge(tracer: Tracer, trace_store: TraceStore) -> None:
    inquiry = asker(tracer, [SEARCH]).ask("q", "test-cap")
    assert inquiry.rounds == agent.ROUNDS
    assert inquiry.result is None
    names = steps(trace_store.read("test-cap"))
    assert names[-1] == "finished"
    assert names.index("nudge") == names.index(f"{agent.ROUNDS} thinking") - 1
    assert trace_store.read("test-cap")[-1].data["status"] is None


def test_verified_comes_from_the_document_status() -> None:
    # Document 10 was read by a parser; 20 was drafted.
    recorder = Recorder()
    verifying = asker(recorder, documents=NoDocuments({10: "confirmed", 20: "draft"}))
    inquiry = Inquiry(correlation_id="x", question="q")
    inquiry.result = Result(
        status=Status.found,
        values=[
            Value(name="parsed", value="1", unit=None, verified=False, source=1),
            Value(name="drafted", value="2", unit=None, verified=True, source=2),
            Value(name="unlisted", value="3", unit=None, verified=True, source=9),
        ],
        passages=[],
        sources=[
            LinkedSource(id=1, document_id=10, kind="invoice", section=None, section_id=None),
            LinkedSource(id=2, document_id=20, kind="receipt", section=None, section_id=None),
        ],
        trace_id="x",
    )
    verifying._verify(inquiry)
    verified: list[bool] = []
    for value in inquiry.result.values:
        verified.append(value.verified)
    assert verified == [True, False, False]
    why: list[str | None] = []
    for value in recorder.events[0].data["values"]:
        why.append(value["document_status"])
    assert why == ["confirmed", "draft", None]


def test_context_goes_into_the_instructions() -> None:
    text = asker(Recorder(), context="Anna è la figlia.")._instructions("x")
    assert "Anna è la figlia." in text
    assert "{context}" not in text
    assert f"{agent.ROUNDS} turni" in text


def test_no_context_leaves_the_slot_empty() -> None:
    text = asker(Recorder())._instructions("x")
    assert "{context}" not in text
