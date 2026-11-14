import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from librarian.evals.retrieval.matching import any_same_value, contains_quote
from librarian.retrieve.result import Result, Status


@dataclass(frozen=True)
class Case:
    file: str
    # Its position in the file, from 0: what --question picks.
    index: int
    question: str
    type: str
    answer: dict[str, Any]
    note: str | None


@dataclass(frozen=True)
class Score:
    # None where the case expects only a status.
    answer: bool | None
    honesty: bool

    @property
    def hit(self) -> bool:
        return self.honesty and self.answer is not False


def load_cases(path: Path) -> list[Case]:
    """One questionnaire file: a JSON array of cases, kept in its order."""
    cases: list[Case] = []
    raws = json.loads(path.read_text(), parse_float=Decimal, parse_int=Decimal)
    for index, raw in enumerate(raws):
        cases.append(
            Case(
                file=path.name,
                index=index,
                question=raw["question"],
                type=raw["type"],
                answer=raw["answer"],
                note=raw.get("note"),
            )
        )
    return cases


def score(case: Case, result: Result) -> Score:
    expected = case.answer

    answer = None
    if "value" in expected:
        answer = any_same_value(expected["value"], expected.get("unit"), result.values)
    elif "quote" in expected:
        # One quote, or several that each prove the answer: any one of them counts.
        quotes = expected["quote"]
        if isinstance(quotes, str):
            quotes = [quotes]
        answer = False
        for quote in quotes:
            if contains_quote(quote, result.passages):
                answer = True

    honesty = result.status == Status(expected.get("status", Status.found))
    return Score(answer, honesty)
