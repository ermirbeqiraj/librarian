import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import simplejson

from librarian.config import EMBEDDER_URL, EVALS_DIR
from librarian.evals.search.runner import load_cases, run

CASES_DIR = EVALS_DIR / "search"
RUNS_DIR = CASES_DIR / "runs"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask every search case and score the hits.")
    parser.add_argument("--mode", choices=["keyword", "vector", "hybrid"], default="hybrid")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    ran_at = datetime.now()
    cases = load_cases(CASES_DIR)
    if not cases:
        raise SystemExit(f"no cases in {CASES_DIR}")
    try:
        outcome = run(args.mode, cases, limit=args.limit)
    except httpx.ConnectError:
        raise SystemExit(
            f"mode {args.mode!r} needs the embedder at {EMBEDDER_URL}; "
            "start compose with the eval profile"
        ) from None
    files: list[str] = []
    for case in cases:
        if case.file not in files:
            files.append(case.file)
    saved = save(
        ran_at,
        {
            "ran_at": ran_at.isoformat(timespec="seconds"),
            "input": {"commit": commit(), "mode": args.mode, "limit": args.limit, "cases": files},
            "result": outcome,
        },
    )
    print(json.dumps(outcome["summary"], ensure_ascii=False))
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
        simplejson.dumps(run_record, indent=2, ensure_ascii=False, use_decimal=True) + "\n"
    )
    return path


if __name__ == "__main__":
    main()
