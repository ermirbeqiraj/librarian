from decimal import Decimal

from librarian.evals.retrieval.runner import Case, run, score
from librarian.retrieve.result import Passage, Result, Source, Status, Value
from librarian.retrieve.retriever import Blank

AMOUNT = Case(
    file="water.json",
    question="quanto ho pagato",
    type="value",
    answer={"value": Decimal("41.27"), "unit": "EUR"},
    documents=["invoice/1.pdf"],
    note=None,
)
SPLIT = Case(
    file="water.json",
    question="quanto ho pagato a luglio",
    type="value",
    answer={"status": "partial", "value": Decimal("41.27"), "unit": "EUR"},
    documents=["invoice/1.pdf"],
    note=None,
)
QUOTE = Case(
    file="water.json",
    question="chi chiamo",
    type="passage",
    answer={"quote": "numero verde 800 000000"},
    documents=["invoice/1.pdf", "invoice/2.pdf"],
    note=None,
)
ABSENT = Case(
    file="water.json",
    question="bolletta 1990",
    type="absence",
    answer={"status": "not_found"},
    documents=[],
    note=None,
)
CASES = [AMOUNT, SPLIT, QUOTE, ABSENT]
GOLD = {"invoice/1.pdf": {11}, "invoice/2.pdf": {12}}


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


class Oracle:
    """Answers each case right, to show the runner takes any retriever."""

    def ask(self, question: str) -> Result:
        if question == ABSENT.question:
            return Result(
                status=Status.not_found, values=[], passages=[], sources=[], trace_id=None
            )
        if question == SPLIT.question:
            return answer(Status.partial, [11])
        return answer(Status.found, [11, 12])


def test_blank_misses_every_case() -> None:
    outcome = run(Blank(), CASES, GOLD)
    assert outcome["summary"]["hit"] == "0/4"
    assert outcome["summary"]["honesty"] == "0/4"


def test_another_retriever_needs_no_change() -> None:
    outcome = run(Oracle(), CASES, GOLD)
    assert outcome["summary"] == {
        "retrieval": "3/3",
        "answer": "3/3",
        "honesty": "4/4",
        "hit": "4/4",
    }


def test_partial_against_found_fails() -> None:
    assert not score(SPLIT, answer(Status.found, [11]), GOLD).hit
    assert not score(AMOUNT, answer(Status.partial, [11]), GOLD).hit


def test_every_gold_document_must_be_a_source() -> None:
    case_score = score(QUOTE, answer(Status.found, [11]), GOLD)
    assert case_score.retrieval is False
    assert case_score.answer is True
    assert not case_score.hit


def test_absence_scores_status_only() -> None:
    case_score = score(ABSENT, answer(Status.not_found, []), GOLD)
    assert case_score.retrieval is None
    assert case_score.answer is None
    assert case_score.hit
