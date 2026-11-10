"""The search eval: asks every case in evals/search/ through `search` and scores the rank
of the first returned section holding a quote (whitespace ignored)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from librarian.evals.retrieval.matching import squeeze
from librarian.retrieve.period import Period
from librarian.retrieve.search import Hit, search

Mode = Literal["keyword", "vector", "hybrid"]


@dataclass(frozen=True)
class Case:
    file: str
    question: str
    quotes: list[str]
    period: Period | None
    author: str
    note: str | None


def load_cases(cases_dir: Path) -> list[Case]:
    cases: list[Case] = []
    for path in sorted(cases_dir.glob("*.json")):
        for raw in json.loads(path.read_text(encoding="utf-8")):
            period = (
                Period(raw["period"]["op"], raw["period"]["value"]) if "period" in raw else None
            )
            cases.append(
                Case(
                    file=path.name,
                    question=raw["question"],
                    quotes=raw["quotes"],
                    period=period,
                    author=raw.get("author", "me"),
                    note=raw.get("note"),
                )
            )
    return cases


def quote_rank(hits: list[Hit], quotes: list[str]) -> tuple[int, Hit | None]:
    """The 1-based rank of the first hit whose text holds a quote; 0 when none does."""
    wanted = [squeeze(quote) for quote in quotes]
    for position, hit in enumerate(hits, start=1):
        if hit.text is None:
            continue
        text = squeeze(hit.text)
        if any(needle in text for needle in wanted):
            return position, hit
    return 0, None


def found_by(hit: Hit | None) -> str | None:
    """Which side found the hit that holds the quote."""
    if hit is None:
        return None
    if hit.keyword_rank is not None and hit.vector_rank is not None:
        return "both"
    if hit.keyword_rank is not None:
        return "keyword"
    if hit.vector_rank is not None:
        return "vector"
    return None


def run(mode: Mode, cases: list[Case], limit: int = 5) -> dict[str, Any]:
    """Asks every case once through `search` and scores it; the question goes in as is."""
    answers: list[dict[str, Any]] = []
    totals = {"top1": [0, 0], "top5": [0, 0]}
    by_author: dict[str, dict[str, list[int]]] = {}
    for case in cases:
        hits = search(case.question, period=case.period, limit=limit, mode=mode)
        rank, hit = quote_rank(hits, case.quotes)
        top1 = rank == 1
        top5 = 0 < rank <= 5
        totals["top1"][1] += 1
        totals["top5"][1] += 1
        totals["top1"][0] += top1
        totals["top5"][0] += top5
        author_totals = by_author.setdefault(case.author, {"top1": [0, 0], "top5": [0, 0]})
        author_totals["top1"][1] += 1
        author_totals["top5"][1] += 1
        author_totals["top1"][0] += top1
        author_totals["top5"][0] += top5
        answers.append(
            {
                "file": case.file,
                "question": case.question,
                "author": case.author,
                "period": (
                    None
                    if case.period is None
                    else {"op": str(case.period.op), "value": case.period.value}
                ),
                "note": case.note,
                "rank": rank,
                "found_by": found_by(hit),
                "top1": top1,
                "top5": top5,
                "hits": [
                    {
                        "section_id": hit.section_id,
                        "document_id": hit.document_id,
                        "kind": hit.kind,
                        "issuer": hit.issuer,
                        "heading": hit.heading,
                        "chars": None if hit.text is None else len(hit.text),
                        "keyword_rank": hit.keyword_rank,
                        "vector_rank": hit.vector_rank,
                    }
                    for hit in hits
                ],
            }
        )
    summary: dict[str, Any] = {name: f"{counts[0]}/{counts[1]}" for name, counts in totals.items()}
    summary["by_author"] = {
        author: {name: f"{counts[0]}/{counts[1]}" for name, counts in counts.items()}
        for author, counts in sorted(by_author.items())
    }
    return {"summary": summary, "answers": answers}
