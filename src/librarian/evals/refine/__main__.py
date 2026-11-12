import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import simplejson

from librarian.config import EVALS_DIR
from librarian.evals.refine.runner import CASES_FILE, load_cases, report, run
from librarian.retrieve.refine import MODEL

CASES_DIR = EVALS_DIR / "refine"
RUNS_DIR = CASES_DIR / "runs"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refine every eval question and score the periods."
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "filter",
        nargs="?",
        default=None,
        help="run only the cases whose question contains this text (case-insensitive)",
    )
    args = parser.parse_args()

    ran_at = datetime.now()
    cases = load_cases(CASES_DIR)
    if args.filter is not None:
        cases = [c for c in cases if args.filter.lower() in c.question.lower()]
        if not cases:
            raise SystemExit(f"no case matches {args.filter!r}")
    if not cases:
        raise SystemExit(f"no cases in {CASES_DIR / CASES_FILE}")
    outcome = run(cases, model_name=args.model)
    for answer in outcome["answers"]:
        print(answer["question"])
        print(json.dumps(answer["produced"], indent=2, ensure_ascii=False))
    saved = save(
        ran_at,
        {
            "ran_at": ran_at.isoformat(timespec="seconds"),
            "input": {
                "commit": commit(),
                "model": args.model,
                "cases": [CASES_FILE],
                "filter": args.filter,
            },
            "result": outcome,
        },
    )
    print(json.dumps(outcome["summary"], ensure_ascii=False))
    print(report(outcome))
    print(saved)


def commit() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    changes = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if changes:
        return head + "-dirty"
    return head


def save(ran_at: datetime, run_record: dict[str, Any]) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{ran_at:%Y-%m-%dT%H-%M-%S}.json"
    path.write_text(
        simplejson.dumps(run_record, indent=2, ensure_ascii=False, use_decimal=True) + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    main()
