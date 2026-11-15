"""Ask a questionnaire through the whole pipeline and score what comes back.

Each run writes runs/run-<time>.md, the summary also printed here, and runs/run-<time>/ with one
file per question and attempt: the case, its marks and the inquiry. Each ask's correlation id is
<run>-q<NN>-r<N>; `librarian-trace <id>` shows every step it went through.
"""

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import simplejson

from librarian.config import EVALS_DIR
from librarian.evals.retrieval.runner import Case, load_cases, score
from librarian.retrieve import ask
from librarian.retrieve.refine import MODEL as REFINE_MODEL

CASES_DIR = EVALS_DIR / "retrieval"
RUNS_DIR = CASES_DIR / "runs"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a questionnaire and score the answers.")
    parser.add_argument(
        "--cases", required=True, help="a file in evals/retrieval/, e.g. cases.json"
    )
    parser.add_argument("--question", type=int, help="only the case at this position, from 0")
    parser.add_argument("--model", required=True, help="the agent's model")
    parser.add_argument("--repeat", type=int, default=1, help="attempts per question")
    args = parser.parse_args()

    cases = load_cases(CASES_DIR / args.cases)
    if args.question is not None:
        cases = [cases[args.question]]

    ran_at = datetime.now()
    name = f"run-{ran_at:%Y-%m-%dT%H-%M-%S}"
    details = RUNS_DIR / name
    details.mkdir(parents=True)

    lines: list[str] = []
    totals = {"hit": [0, 0], "answer": [0, 0], "honesty": [0, 0]}
    tokens_in = 0
    tokens_out = 0
    started = time.monotonic()
    for case in cases:
        for attempt in range(1, args.repeat + 1):
            line, marks, inquiry = _ask(case, args.model, attempt, name, details)
            lines.append(line)
            for mark_name, mark in marks.items():
                if mark is not None:
                    totals[mark_name][1] += 1
                    if mark:
                        totals[mark_name][0] += 1
            tokens_in += inquiry.tokens_in
            tokens_out += inquiry.tokens_out
    seconds = round(time.monotonic() - started)

    question = "all" if args.question is None else str(args.question)
    hit = _ratio(totals["hit"])
    answer = _ratio(totals["answer"])
    honesty = _ratio(totals["honesty"])
    summary = [
        f"# {name}",
        "",
        f"- cases: {args.cases}, question: {question}, repeat: {args.repeat}",
        f"- model: {args.model} · reasoning: {ask.REASONING_EFFORT} · prompt: {ask.INSTRUCTIONS.name} · refine: {REFINE_MODEL}",
        f"- commit: {ask.git_sha()}",
        f"- score: hit {hit} · answer {answer} · honesty {honesty}",
        f"- tokens: in {tokens_in}, out {tokens_out} · time: {seconds} s",
        "",
        "| # | try | mark | status | rounds | calls | tokens in/out | s | id | question |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    text = "\n".join(summary + lines) + "\n"
    (RUNS_DIR / f"{name}.md").write_text(text, encoding="utf-8")
    print(text)
    print(RUNS_DIR / f"{name}.md")


def _ask(
    case: Case, model: str, attempt: int, run: str, details: Path
) -> tuple[str, dict[str, bool | None], ask.Inquiry]:
    # One id per ask: repeats of a question would mix under one.
    correlation_id = f"{run}-q{case.index:02d}-r{attempt}"
    inquiry = ask.ask(case.question, model, correlation_id)
    marks: dict[str, bool | None] = {"hit": False, "answer": None, "honesty": False}
    status = "no submit"
    if inquiry.result is not None:
        case_score = score(case, inquiry.result)
        marks = {"hit": case_score.hit, "answer": case_score.answer, "honesty": case_score.honesty}
        status = str(inquiry.result.status)
    record: dict[str, Any] = {
        "case": {
            "file": case.file,
            "index": case.index,
            "question": case.question,
            "type": case.type,
            "expected": case.answer,
        },
        "attempt": attempt,
        "marks": marks,
        "inquiry": inquiry.model_dump(mode="json", by_alias=True),
    }
    path = details / f"{case.index:02d}-{attempt}.json"
    path.write_text(
        simplejson.dumps(record, indent=2, ensure_ascii=False, use_decimal=True) + "\n",
        encoding="utf-8",
    )
    mark = "HIT" if marks["hit"] else "miss"
    line = (
        f"| {case.index} | {attempt} | {mark} | {status} | {inquiry.rounds} | {inquiry.calls} "
        f"| {inquiry.tokens_in}/{inquiry.tokens_out} | {round(inquiry.ms / 1000)} "
        f"| {correlation_id} | {case.question} |"
    )
    return line, marks, inquiry


def _ratio(counts: list[int]) -> str:
    return f"{counts[0]}/{counts[1]}"


if __name__ == "__main__":
    main()
