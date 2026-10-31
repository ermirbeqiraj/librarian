import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from librarian.evals.retrieval.matching import any_same_value, contains_quote
from librarian.retrieve.result import Result, Status
from librarian.retrieve.retriever import Retriever


@dataclass(frozen=True)
class Case:
    file: str
    question: str
    type: str
    answer: dict[str, Any]
    documents: list[str]
    note: str | None


@dataclass(frozen=True)
class Score:
    # None where the case has nothing to score: no gold documents, or only a status.
    retrieval: bool | None
    answer: bool | None
    honesty: bool

    @property
    def hit(self) -> bool:
        return self.honesty and self.retrieval is not False and self.answer is not False


def load_cases(cases_dir: Path) -> list[Case]:
    cases: list[Case] = []
    for path in sorted(cases_dir.glob("*.json")):
        for raw in json.loads(path.read_text(), parse_float=Decimal, parse_int=Decimal):
            cases.append(
                Case(
                    file=path.name,
                    question=raw["question"],
                    type=raw["type"],
                    answer=raw["answer"],
                    documents=raw["documents"],
                    note=raw.get("note"),
                )
            )
    return cases


def gold_paths(cases: list[Case]) -> list[str]:
    paths: list[str] = []
    for case in cases:
        for path in case.documents:
            if path not in paths:
                paths.append(path)
    return paths


def score(case: Case, result: Result, gold: dict[str, set[int]]) -> Score:
    expected = case.answer

    retrieval = None
    if case.documents:
        source_ids: set[int] = set()
        for source in result.sources:
            source_ids.add(source.document_id)
        retrieval = True
        for path in case.documents:
            if not gold[path] & source_ids:
                retrieval = False

    answer = None
    if "value" in expected:
        answer = any_same_value(expected["value"], expected.get("unit"), result.values)
    elif "quote" in expected:
        answer = contains_quote(expected["quote"], result.passages)

    honesty = result.status == Status(expected.get("status", Status.found))
    return Score(retrieval, answer, honesty)


def run(retriever: Retriever, cases: list[Case], gold: dict[str, set[int]]) -> dict[str, Any]:
    """Asks every question once and scores it; gold maps each case path to its document ids."""
    answers: list[dict[str, Any]] = []
    totals = {"retrieval": [0, 0], "answer": [0, 0], "honesty": [0, 0], "hit": [0, 0]}
    for case in cases:
        result = retriever.ask(case.question)
        case_score = score(case, result, gold)
        marks = {
            "retrieval": case_score.retrieval,
            "answer": case_score.answer,
            "honesty": case_score.honesty,
            "hit": case_score.hit,
        }
        for name, mark in marks.items():
            if mark is not None:
                totals[name][1] += 1
                if mark:
                    totals[name][0] += 1
        answers.append(
            {
                "file": case.file,
                "question": case.question,
                "type": case.type,
                "expected": case.answer,
                "documents": case.documents,
                "got": result.model_dump(mode="json"),
                "marks": marks,
            }
        )

    summary: dict[str, str] = {}
    for name, counts in totals.items():
        summary[name] = f"{counts[0]}/{counts[1]}"
    return {"summary": summary, "answers": answers}
