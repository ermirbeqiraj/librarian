from datetime import date
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from librarian.retrieve.refine import QueryPeriod, Refined, refine

QUESTION = "quanto ho pagato x gas nel 2026 e l acqua?"
TODAY = date(2026, 11, 11)


def valid_args() -> dict[str, Any]:
    return {
        "user_query": QUESTION,
        "queries": [
            {
                "text": "Quanto ho pagato per il gas nel 2026?",
                "period": {"from": "2026-01-01", "to": "2026-11-11"},
            },
            {
                "text": "Quanto ho pagato per l'acqua nel 2026?",
                "period": {"from": "2026-01-01", "to": "2026-11-11"},
            },
        ],
    }


def invalid_args(args: dict[str, Any]) -> dict[str, Any]:
    try:
        Refined.model_validate(args)
    except ValidationError as error:
        raw = AIMessage(content="", tool_calls=[{"name": "Refined", "args": args, "id": "1"}])
        return {"raw": raw, "parsed": None, "parsing_error": error}
    raise AssertionError("expected the args to be invalid")


def valid() -> dict[str, Any]:
    args = {**valid_args(), "user_query": "not the question as it came"}
    return {
        "raw": AIMessage(content=""),
        "parsed": Refined.model_validate(args),
        "parsing_error": None,
    }


def bad_json() -> dict[str, Any]:
    return {
        "raw": AIMessage(content="{not json"),
        "parsed": None,
        "parsing_error": ValueError("Expecting value: line 1 column 2 (char 1)"),
    }


def model(answers: list[dict[str, Any]], asked: list[list[tuple[str, str]]]) -> Any:
    def answer(messages: list[tuple[str, str]]) -> dict[str, Any]:
        asked.append(list(messages))
        return answers.pop(0)

    return RunnableLambda(answer)


def test_a_valid_answer_parses() -> None:
    asked: list[list[tuple[str, str]]] = []
    refined = refine(QUESTION, TODAY, model=model([valid()], asked))
    assert refined == Refined.model_validate(valid_args())
    # The question as it came is set by code, not taken from the model.
    assert refined.user_query == QUESTION
    assert len(asked) == 1
    system, human = asked[0]
    assert system[0] == "system" and TODAY.isoformat() in system[1]
    assert human == ("human", QUESTION)


def test_bad_json_is_retried() -> None:
    asked: list[list[tuple[str, str]]] = []
    refined = refine(QUESTION, TODAY, model=model([bad_json(), valid()], asked), max_retries=2)
    assert refined.queries[0].period == QueryPeriod(from_=date(2026, 1, 1), to=date(2026, 11, 11))
    assert len(asked) == 2
    assert asked[1][2] == ("ai", "{not json")
    assert asked[1][3][0] == "human" and "Expecting value" in asked[1][3][1]


def test_a_fake_date_is_retried() -> None:
    args = valid_args()
    args["queries"][0]["period"] = {"from": "2026-02-30", "to": "2026-03-01"}
    asked: list[list[tuple[str, str]]] = []
    refine(QUESTION, TODAY, model=model([invalid_args(args), valid()], asked), max_retries=2)
    assert len(asked) == 2
    assert "period" in asked[1][3][1]


def test_from_after_to_is_retried() -> None:
    args = valid_args()
    args["queries"][0]["period"] = {"from": "2026-05-10", "to": "2026-05-01"}
    asked: list[list[tuple[str, str]]] = []
    refine(QUESTION, TODAY, model=model([invalid_args(args), valid()], asked), max_retries=2)
    assert len(asked) == 2
    assert "is after" in asked[1][3][1]


def test_a_second_failure_raises_a_readable_error() -> None:
    args = valid_args()
    args["queries"][0]["period"] = {"from": "2026-05-10", "to": "2026-05-01"}
    asked: list[list[tuple[str, str]]] = []
    with pytest.raises(ValidationError, match="'from' 2026-05-10 is after 'to' 2026-05-01"):
        refine(
            QUESTION,
            TODAY,
            model=model([invalid_args(args), invalid_args(args)], asked),
            max_retries=1,
        )
    assert len(asked) == 2


def test_the_json_shape() -> None:
    refined = Refined.model_validate(valid_args())
    dumped = refined.model_dump(mode="json", by_alias=True)
    assert dumped["queries"][0]["period"] == {"from": "2026-01-01", "to": "2026-11-11"}
    open_start = Refined.model_validate(
        {
            "user_query": "q",
            "queries": [{"text": "t", "period": {"from": None, "to": "2026-03-31"}}],
        }
    )
    assert open_start.queries[0].period is not None
    assert open_start.queries[0].period.from_ is None
    assert open_start.queries[0].period.to == date(2026, 3, 31)
    no_period = Refined.model_validate(
        {"user_query": "q", "queries": [{"text": "t", "period": None}]}
    )
    assert no_period.queries[0].period is None
