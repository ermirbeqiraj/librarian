import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

import librarian.evals.retrieval.__main__ as eval_retrieval
from librarian.evals.retrieval.runner import Case, load_cases, score
from librarian.retrieve import ask
from librarian.retrieve.ask import Inquiry
from librarian.retrieve.result import Passage, Result, Source, Status, Value

AMOUNT = Case(
    file="water.json",
    index=0,
    question="quanto ho pagato",
    type="value",
    answer={"value": Decimal("41.27"), "unit": "EUR"},
    note=None,
)
SPLIT = Case(
    file="water.json",
    index=0,
    question="quanto ho pagato a luglio",
    type="value",
    answer={"status": "partial", "value": Decimal("41.27"), "unit": "EUR"},
    note=None,
)
QUOTE = Case(
    file="water.json",
    index=0,
    question="chi chiamo",
    type="passage",
    answer={"quote": "numero verde 800 000000"},
    note=None,
)
ABSENT = Case(
    file="water.json",
    index=0,
    question="bolletta 1990",
    type="absence",
    answer={"status": "not_found"},
    note=None,
)
CASES = [AMOUNT, SPLIT, QUOTE, ABSENT]


def answer(status: Status | None, document_ids: list[int]) -> Result:
    sources: list[Source] = []
    for document_id in document_ids:
        sources.append(
            Source(id=document_id, document_id=document_id, kind="bill", section=None, page=1)
        )
    return Result(
        status=status,
        values=[Value(name="total", value="41,27 €", unit=None, verified=False, source=11)],
        passages=[Passage(text="chiami il numero verde 800 000000", source=11)],
        sources=sources,
        trace_id=None,
    )


def test_partial_against_found_fails() -> None:
    assert not score(SPLIT, answer(Status.found, [11])).hit
    assert not score(AMOUNT, answer(Status.partial, [11])).hit


def test_any_of_several_quotes_counts() -> None:
    either = Case(
        file="water.json",
        index=0,
        question="chi chiamo",
        type="passage",
        answer={"quote": ["pronto intervento 800 111111", "numero verde 800 000000"]},
        note=None,
    )
    neither = Case(
        file="water.json",
        index=0,
        question="chi chiamo",
        type="passage",
        answer={"quote": ["pronto intervento 800 111111", "numero verde 800 222222"]},
        note=None,
    )
    assert score(either, answer(Status.found, [11])).hit
    assert not score(neither, answer(Status.found, [11])).hit


def test_absence_scores_status_only() -> None:
    case_score = score(ABSENT, answer(Status.not_found, []))
    assert case_score.answer is None
    assert case_score.hit


def test_cases_keep_their_position_in_the_file(tmp_path: Path) -> None:
    path = tmp_path / "water.json"
    path.write_text(
        json.dumps(
            [
                {"question": "prima", "type": "value", "answer": {"value": 1}},
                {"question": "seconda", "type": "absence", "answer": {"status": "not_found"}},
            ]
        )
    )
    cases = load_cases(path)
    assert [(case.index, case.question) for case in cases] == [(0, "prima"), (1, "seconda")]


def test_a_question_that_errors_is_skipped_and_the_run_goes_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_ask(question: str, model: str, correlation_id: str) -> Inquiry:
        if question == "prima":
            raise RuntimeError("429 Too Many Requests")
        inquiry = Inquiry(correlation_id=correlation_id, question=question)
        inquiry.result = answer(Status.not_found, [])
        return inquiry

    cases = [
        {"question": "prima", "type": "absence", "answer": {"status": "not_found"}},
        {"question": "seconda", "type": "absence", "answer": {"status": "not_found"}},
    ]
    (tmp_path / "cases.json").write_text(json.dumps(cases))
    monkeypatch.setattr(eval_retrieval, "CASES_DIR", tmp_path)
    monkeypatch.setattr(eval_retrieval, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(ask, "ask", fake_ask)
    argv = ["librarian-eval-retrieval", "--cases", "cases.json", "--model", "fake"]
    monkeypatch.setattr(sys, "argv", argv)
    eval_retrieval.main()

    summary = next((tmp_path / "runs").glob("*.md")).read_text()
    assert "- score: hit 1/1 · answer 0/0 · honesty 1/1 · skipped 1\n" in summary
    assert re.search(
        r"\| 0 \| 1 \| skipped \| RuntimeError \|.*\| run-\S+-q00-r1 \| prima \|", summary
    )
    assert "| 1 | 1 | HIT | not_found |" in summary
    record = json.loads(next((tmp_path / "runs").glob("run-*/00-1.json")).read_text())
    assert record["marks"] == {"hit": None, "answer": None, "honesty": None}
    assert record["error"] == "RuntimeError: 429 Too Many Requests"
    assert "inquiry" not in record
