import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import RefusingStore
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy import select

import librarian.evals.retrieval.__main__ as eval_retrieval
import librarian.retrieve.trace.__main__ as trace_command
from librarian.models import Ask, AskStatus
from librarian.retrieve import ask
from librarian.retrieve.ask import Inquiry
from librarian.retrieve.refine import Query, Refined
from librarian.retrieve.result import LinkedSource, Result, Status, Value
from librarian.retrieve.schema import Schema
from librarian.retrieve.sql import SqlResult
from librarian.retrieve.trace import tracer
from librarian.retrieve.trace.tracer import Event, PostgresStore, Store

USAGE = {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
SEARCH = {"name": "search", "args": {"query": "bolletta"}}
SUBMIT = {
    "name": "submit",
    "args": {"status": "not_found", "values": [], "passages": [], "sources": []},
}


class FakeChat:
    """Answers each round with the next tool call of a script; past its end, repeats the last.
    A script entry that is an exception is raised instead."""

    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.round = 0

    def bind_tools(self, tools: list[Any], tool_choice: str | None = None) -> "FakeChat":
        return self

    def invoke(self, messages: list[Any]) -> AIMessage:
        call = self.script[min(self.round, len(self.script) - 1)]
        self.round += 1
        if isinstance(call, Exception):
            raise call
        thinking = {
            "type": "thinking",
            "thinking": [{"type": "text", "text": f"step {self.round}"}],
        }
        return AIMessage(
            content=[thinking],
            tool_calls=[{**call, "id": f"call-{self.round}"}],
            usage_metadata=USAGE,
        )


def fake_sql(query: str) -> SqlResult:
    if "boom" in query:
        return SqlResult(error='syntax error at or near "boom"')
    # A float: Postgres gives it back as a Decimal.
    return SqlResult(columns=["share"], rows=[{"share": 0.5}])


def fake_refine_model(schema: Any, model_name: str) -> RunnableLambda[Any, Any]:
    def answer(messages: Any) -> dict[str, Any]:
        refined = Refined(user_query="q", queries=[Query(text="bolletta corretta")])
        return {
            "raw": AIMessage(content="", usage_metadata=USAGE),
            "parsed": refined,
            "parsing_error": None,
        }

    return RunnableLambda(answer)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """Every outside call of `ask` faked; returns a function that sets the agent's script."""
    monkeypatch.setattr(ask.mistral, "structured", fake_refine_model)
    monkeypatch.setattr(ask, "run_sql", fake_sql)
    monkeypatch.setattr(ask, "schema", lambda: Schema(tables=[], field_keys=[]))
    monkeypatch.setattr(ask, "CONTEXT_FILE", tmp_path / "missing.md")
    monkeypatch.setattr(ask, "search", lambda *args, **kwargs: [])
    monkeypatch.setattr(ask, "_statuses", lambda document_ids: {})
    monkeypatch.setattr(ask, "sections", lambda document_id: None)
    monkeypatch.setattr(ask, "_paths", lambda document_ids: {})

    def script(calls: list[Any]) -> None:
        chat = FakeChat(calls)
        monkeypatch.setattr(ask, "ChatMistralAI", lambda **kwargs: chat)

    return script


def steps(events: list[Event]) -> list[str]:
    names: list[str] = []
    for event in events:
        if event.round is None:
            names.append(event.step)
        else:
            names.append(f"{event.round} {event.kind}")
    return names


def asks_row(store: Store) -> Ask | None:
    """The run's asks row when the store is Postgres, None for files."""
    if not isinstance(store, PostgresStore):
        return None
    with ask.Session() as session:
        return session.scalars(select(Ask)).one()


def test_a_run_that_submits_leaves_every_event_in_order(trace_store: Store, fakes: Any) -> None:
    fakes([SEARCH, SUBMIT])
    inquiry = ask.ask("qnd scade la bolletta", "fake", "test-submits")
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
    trace_store: Store, fakes: Any
) -> None:
    fakes([SEARCH, RuntimeError("429 Too Many Requests")])
    with pytest.raises(RuntimeError, match="429"):
        ask.ask("qnd scade la bolletta", "fake", "test-fails")
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


def test_a_store_that_is_down_never_breaks_the_ask(
    trace_store: Store, fakes: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracer, "store", RefusingStore(trace_store, times=99))
    fakes([SUBMIT])
    inquiry = ask.ask("q", "fake", "test-store-down")
    assert inquiry.result is not None
    fakes([RuntimeError("429 Too Many Requests")])
    with pytest.raises(RuntimeError, match="429"):
        ask.ask("q", "fake", "test-store-down-fails")
    monkeypatch.setattr(tracer, "store", trace_store)
    tracer.flush()
    assert trace_store.read("test-store-down")[-1].step == "finished"
    assert trace_store.read("test-store-down-fails")[-1].step == "failed"


def test_a_tool_error_lands_in_its_tool_result_and_the_run_goes_on(
    trace_store: Store, fakes: Any
) -> None:
    fakes(
        [
            {"name": "sql", "args": {"query": "boom"}},
            {"name": "search", "args": {}},
            {"name": "nope", "args": {}},
            SUBMIT,
        ]
    )
    ask.ask("q", "fake", "test-tool-error")
    errors: list[str | None] = []
    for event in trace_store.read("test-tool-error"):
        if event.kind == "tool_result":
            errors.append(event.data["error"])
    assert errors[0] == 'syntax error at or near "boom"'
    assert errors[1] is not None and "query" in errors[1]
    assert errors[2] is not None and "non esiste" in errors[2]
    assert errors[3] is None
    assert trace_store.read("test-tool-error")[-1].step == "finished"


def test_dig_stops_at_the_cap_after_the_nudge(trace_store: Store, fakes: Any) -> None:
    fakes([SEARCH])
    inquiry = ask.ask("q", "fake", "test-cap")
    assert inquiry.rounds == ask.ROUNDS
    assert inquiry.result is None
    names = steps(trace_store.read("test-cap"))
    assert names[-1] == "finished"
    assert names.index("nudge") == names.index(f"{ask.ROUNDS} thinking") - 1
    assert trace_store.read("test-cap")[-1].data["status"] is None


def test_the_eval_names_each_ask_and_the_trace_opens_it(
    trace_store: Store,
    fakes: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fakes([SUBMIT])
    cases = [
        {"question": "la bolletta del 1990", "type": "absence", "answer": {"status": "not_found"}}
    ]
    (tmp_path / "cases.json").write_text(json.dumps(cases))
    monkeypatch.setattr(eval_retrieval, "CASES_DIR", tmp_path)
    monkeypatch.setattr(eval_retrieval, "RUNS_DIR", tmp_path / "runs")
    argv = [
        "librarian-eval-retrieval",
        "--cases",
        "cases.json",
        "--model",
        "fake",
        "--question",
        "0",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    eval_retrieval.main()
    summary = next((tmp_path / "runs").glob("*.md")).read_text()
    found = re.search(r"\| (run-\S+-q00-r1) \|", summary)
    assert found is not None
    correlation_id = found.group(1)
    record = json.loads(next((tmp_path / "runs").glob("run-*/00-1.json")).read_text())
    assert record["inquiry"]["correlation_id"] == correlation_id
    capsys.readouterr()

    monkeypatch.setattr(sys, "argv", ["librarian-trace", correlation_id])
    trace_command.main()
    printed = capsys.readouterr().out
    assert printed.startswith(correlation_id)
    assert "  round 1\n    thinking" in printed
    assert "\n  finished (" in printed


def test_verified_comes_from_the_document_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_statuses(document_ids: list[int]) -> dict[int, str]:
        # Document 10 was read by a parser; 20 was drafted.
        assert document_ids == [10, 20]
        return {10: "confirmed", 20: "draft"}

    traced: list[Event] = []
    monkeypatch.setattr(ask, "_statuses", fake_statuses)
    monkeypatch.setattr(ask, "trace", lambda correlation_id, event: traced.append(event))
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
    ask._verify(inquiry)
    verified: list[bool] = []
    for value in inquiry.result.values:
        verified.append(value.verified)
    assert verified == [True, False, False]
    why: list[str | None] = []
    for value in traced[0].data["values"]:
        why.append(value["document_status"])
    assert why == ["confirmed", "draft", None]


def _instructions_with(monkeypatch: pytest.MonkeyPatch, context_file: Path) -> str:
    monkeypatch.setattr(ask, "CONTEXT_FILE", context_file)
    monkeypatch.setattr(ask, "run_sql", lambda query: SqlResult(columns=[], rows=[]))
    monkeypatch.setattr(ask, "schema", lambda: Schema(tables=[], field_keys=[]))
    monkeypatch.setattr(ask, "trace", lambda correlation_id, event: None)
    return ask._instructions("x")


def test_context_goes_into_the_instructions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context_file = tmp_path / "context.md"
    context_file.write_text("Anna è la figlia.\n")
    text = _instructions_with(monkeypatch, context_file)
    assert "Anna è la figlia." in text
    assert "{context}" not in text
    assert f"{ask.ROUNDS} turni" in text


def test_no_context_file_leaves_the_slot_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    text = _instructions_with(monkeypatch, tmp_path / "missing.md")
    assert "{context}" not in text
