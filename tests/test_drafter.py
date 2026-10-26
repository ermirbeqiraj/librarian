from datetime import date
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from librarian.ingest.drafter.drafter import _ask  # pyright: ignore[reportPrivateUsage]
from librarian.ingest.drafter.schema import Draft, Validity
from librarian.models.document_kind import DocumentKind

DRAFT = Draft(
    kind=DocumentKind.receipt,
    validity=Validity(start=date(2030, 10, 7), end=None, as_written="07/10/2030"),
    fields=[],
    description="",
)
NULL_VALUE = {"name": "f", "value": None, "as_written": "x"}


def invalid() -> dict[str, Any]:
    args = {**DRAFT.model_dump(mode="json"), "fields": [NULL_VALUE]}
    try:
        Draft.model_validate(args)
    except ValidationError as error:
        raw = AIMessage(content="", tool_calls=[{"name": "Draft", "args": args, "id": "1"}])
        return {"raw": raw, "parsed": None, "parsing_error": error}
    raise AssertionError("expected the args to be invalid")


def valid() -> dict[str, Any]:
    return {"raw": AIMessage(content=""), "parsed": DRAFT, "parsing_error": None}


def model(answers: list[dict[str, Any]], asked: list[list[tuple[str, str]]]) -> Any:
    def answer(messages: list[tuple[str, str]]) -> dict[str, Any]:
        asked.append(list(messages))
        return answers.pop(0)

    return RunnableLambda(answer)


def test_asks_again_when_the_answer_does_not_fit_the_schema() -> None:
    asked: list[list[tuple[str, str]]] = []
    messages = [("human", "page")]
    assert _ask(model([invalid(), valid()], asked), messages, max_retries=2) == DRAFT
    assert len(asked) == 2
    assert asked[1][1][0] == "ai" and '"value": null' in asked[1][1][1]
    assert asked[1][2][0] == "human" and "fields.0.value" in asked[1][2][1]
    assert messages == [("human", "page")]


def test_raises_the_schema_error_after_the_retries() -> None:
    asked: list[list[tuple[str, str]]] = []
    with pytest.raises(ValidationError, match="fields.0.value"):
        _ask(model([invalid(), invalid(), invalid()], asked), [("human", "page")], max_retries=2)
    assert len(asked) == 3
