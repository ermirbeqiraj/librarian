from datetime import date
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from librarian.retrieve import ask
from librarian.retrieve.ask import Inquiry
from librarian.retrieve.refine import Query, Refined
from librarian.retrieve.result import Result, Source, Status, Value
from librarian.retrieve.schema import Schema
from librarian.retrieve.sql import SqlResult

SUBMITTED = Result(status=Status.not_found, values=[], passages=[], sources=[], trace_id=None)


def test_the_steps_run_in_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    steps: list[str] = []

    def fake_refine(question: str, today: date) -> Refined:
        steps.append("refine")
        return Refined(user_query=question, queries=[Query(text=question)])

    def fake_dig(inquiry: Inquiry) -> None:
        steps.append("dig")
        assert inquiry.refined is not None
        inquiry.result = SUBMITTED

    monkeypatch.setattr(ask, "refine", fake_refine)
    monkeypatch.setattr(ask, "_dig", fake_dig)
    monkeypatch.setattr(ask, "ASKS_DIR", tmp_path)
    result = ask.ask("qnd scade la bolletta", "fake").result
    assert steps == ["refine", "dig"]
    assert result == SUBMITTED
    saved = list(tmp_path.glob("*.json"))
    assert len(saved) == 1
    assert Inquiry.model_validate_json(saved[0].read_text()).result == SUBMITTED


class FakeChat:
    """Answers each round with the next tool call of a script; past its end, repeats the last."""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        self.script = script
        self.round = 0

    def bind_tools(self, tools: list[Any], tool_choice: str | None = None) -> "FakeChat":
        return self

    def invoke(self, messages: list[Any]) -> AIMessage:
        call = self.script[min(self.round, len(self.script) - 1)]
        self.round += 1
        thinking = {
            "type": "thinking",
            "thinking": [{"type": "text", "text": f"step {self.round}"}],
        }
        return AIMessage(content=[thinking], tool_calls=[{**call, "id": f"call-{self.round}"}])


SEARCH = {"name": "search", "args": {"query": "bolletta"}}
SUBMIT = {
    "name": "submit",
    "args": {"status": "not_found", "values": [], "passages": [], "sources": []},
}


def _dig_with(monkeypatch: pytest.MonkeyPatch, script: list[dict[str, Any]]) -> Inquiry:
    chat = FakeChat(script)
    monkeypatch.setattr(ask, "ChatMistralAI", lambda **kwargs: chat)
    monkeypatch.setattr(ask, "_instructions", lambda: "")
    monkeypatch.setattr(ask, "search", lambda *args, **kwargs: [])
    inquiry = Inquiry(id="x", model="fake", question="q", today=date(2026, 11, 14))
    inquiry.refined = Refined(user_query="q", queries=[Query(text="q")])
    ask._dig(inquiry)
    return inquiry


def test_dig_keeps_each_round_with_its_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    inquiry = _dig_with(monkeypatch, [SEARCH, SEARCH, SUBMIT])
    thoughts: list[str] = []
    tools: list[str] = []
    for each in inquiry.rounds:
        thoughts.append(each.thinking)
        for call in each.calls:
            tools.append(call.tool)
    assert thoughts == ["step 1", "step 2", "step 3"]
    assert tools == ["search", "search", "submit"]
    assert inquiry.result == SUBMITTED


def test_an_unknown_tool_goes_back_to_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    inquiry = _dig_with(monkeypatch, [{"name": "nope", "args": {}}, SUBMIT])
    assert "non esiste" in inquiry.rounds[0].calls[0].output
    assert inquiry.result == SUBMITTED


def test_dig_stops_at_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    inquiry = _dig_with(monkeypatch, [SEARCH])
    assert len(inquiry.rounds) == ask.ROUNDS
    assert inquiry.result is None


def test_verified_comes_from_the_document_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_confirmed(document_ids: list[int]) -> set[int]:
        # Document 10 was read by a parser; 20 was drafted.
        assert document_ids == [10, 20]
        return {10}

    monkeypatch.setattr(ask, "_confirmed", fake_confirmed)
    inquiry = Inquiry(id="x", model="fake", question="q", today=date(2026, 11, 14))
    inquiry.result = Result(
        status=Status.found,
        values=[
            Value(name="parsed", value="1", unit=None, verified=False, source=1),
            Value(name="drafted", value="2", unit=None, verified=True, source=2),
            Value(name="unlisted", value="3", unit=None, verified=True, source=9),
        ],
        passages=[],
        sources=[
            Source(id=1, document_id=10, kind="invoice", section=None),
            Source(id=2, document_id=20, kind="receipt", section=None),
        ],
        trace_id=None,
    )
    ask._verify(inquiry)
    verified: list[bool] = []
    for value in inquiry.result.values:
        verified.append(value.verified)
    assert verified == [True, False, False]


def _instructions_with(monkeypatch: pytest.MonkeyPatch, context_file: Path) -> str:
    monkeypatch.setattr(ask, "CONTEXT_FILE", context_file)
    monkeypatch.setattr(ask, "run_sql", lambda query: SqlResult(columns=[], rows=[]))
    monkeypatch.setattr(ask, "schema", lambda: Schema(tables=[], field_keys=[]))
    return ask._instructions()


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
