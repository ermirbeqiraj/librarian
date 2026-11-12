"""The refine eval: asks every case in evals/refine/questions.json through `refine` with
the case's own `today`, and scores the number of queries per case and each query's exact
period. The produced text is not scored; it is written next to the expected one to read.
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from librarian.retrieve.refine import MODEL, Query, refine

CASES_FILE = "questions.json"

# A period as the gold writes it: (from, to), either None; None itself when the
# question names no time.
Period = tuple[date | None, date | None] | None


@dataclass(frozen=True)
class ExpectedQuery:
    text: str
    period: Period


@dataclass(frozen=True)
class Case:
    file: str
    question: str
    today: date
    queries: list[ExpectedQuery]
    author: str
    note: str | None


def load_cases(cases_dir: Path) -> list[Case]:
    cases: list[Case] = []
    path = cases_dir / CASES_FILE
    for raw in json.loads(path.read_text(encoding="utf-8")):
        cases.append(
            Case(
                file=path.name,
                question=raw["question"],
                today=date.fromisoformat(raw["today"]),
                queries=[
                    ExpectedQuery(text=query["text"], period=_gold_period(query["period"]))
                    for query in raw["queries"]
                ],
                author=raw.get("author", "me"),
                note=raw.get("note"),
            )
        )
    return cases


def run(cases: list[Case], model_name: str = MODEL) -> dict[str, Any]:
    """Refines every case once with its own `today` and scores it."""
    answers: list[dict[str, Any]] = []
    count_ok = 0
    period_ok = 0
    period_total = 0
    for case in cases:
        refined = refine(case.question, case.today, model_name=model_name)
        count = len(refined.queries) == len(case.queries)
        count_ok += count
        queries: list[dict[str, Any]] = []
        for index in range(max(len(case.queries), len(refined.queries))):
            expected = case.queries[index] if index < len(case.queries) else None
            produced = refined.queries[index] if index < len(refined.queries) else None
            ok = (
                expected is not None
                and produced is not None
                and _period(produced) == (expected.period)
            )
            if expected is not None:
                period_total += 1
                period_ok += ok
            queries.append(
                {
                    "expected_text": expected.text if expected else None,
                    "text": produced.text if produced else None,
                    "expected_period": _json_period(expected.period if expected else None),
                    "period": _json_period(_period(produced) if produced else None),
                    "period_ok": ok,
                }
            )
        answers.append(
            {
                "file": case.file,
                "question": case.question,
                "today": case.today.isoformat(),
                "author": case.author,
                "note": case.note,
                "produced": refined.model_dump(by_alias=True, mode="json"),
                "user_query": refined.user_query,
                "query_count_ok": count,
                "expected_count": len(case.queries),
                "produced_count": len(refined.queries),
                "queries": queries,
            }
        )
    summary = {
        "query_count": f"{count_ok}/{len(cases)}",
        "period": f"{period_ok}/{period_total}",
    }
    return {"summary": summary, "answers": answers}


def report(outcome: dict[str, Any]) -> str:
    """Every case with the expected text next to the produced one; text is read, not scored."""
    lines: list[str] = []
    for answer in outcome["answers"]:
        count = f"{answer['produced_count']}/{answer['expected_count']}"
        mark = "ok" if answer["query_count_ok"] else "COUNT"
        lines.append(f"{answer['question']}  [queries {count} {mark}]")
        if answer["note"]:
            lines.append(f"  note: {answer['note']}")
        for query in answer["queries"]:
            mark = "ok" if query["period_ok"] else "PERIOD"
            expected = _fmt_period(query["expected_period"])
            produced = _fmt_period(query["period"])
            lines.append(f"  {mark} {expected} -> {produced}")
            lines.append(f"    expected: {query['expected_text']}")
            lines.append(f"    got:      {query['text']}")
    return "\n".join(lines)


def _gold_period(raw: dict[str, Any] | None) -> Period:
    if raw is None:
        return None
    return (
        date.fromisoformat(raw["from"]) if raw["from"] is not None else None,
        date.fromisoformat(raw["to"]) if raw["to"] is not None else None,
    )


def _period(query: Query) -> Period:
    if query.period is None:
        return None
    return query.period.from_, query.period.to


def _json_period(period: Period) -> dict[str, str | None] | None:
    if period is None:
        return None
    from_, to = period
    return {
        "from": from_.isoformat() if from_ is not None else None,
        "to": to.isoformat() if to is not None else None,
    }


def _fmt_period(period: dict[str, str | None] | None) -> str:
    if period is None:
        return "no period"
    return f"{period['from']}..{period['to']}"
