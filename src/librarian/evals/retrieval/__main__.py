import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import simplejson
from sqlalchemy import select

from librarian.config import EVALS_DIR, LEARNINGS_DIR
from librarian.db import Session
from librarian.evals.retrieval.runner import gold_paths, load_cases, run
from librarian.models import Document, Ingestion
from librarian.retrieve.retriever import Blank, Retriever

CASES_DIR = EVALS_DIR / "retrieval"
RUNS_DIR = LEARNINGS_DIR / "evals" / "retrieval"
RETRIEVERS: dict[str, type[Retriever]] = {"blank": Blank}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask every retrieval case and score the answers.")
    parser.add_argument("--retriever", choices=RETRIEVERS, default="blank")
    args = parser.parse_args()

    ran_at = datetime.now()
    cases = load_cases(CASES_DIR)
    if not cases:
        raise SystemExit(f"no cases in {CASES_DIR}")
    paths = gold_paths(cases)
    gold = resolve(paths)
    missing: list[str] = []
    for path in paths:
        if path not in gold:
            missing.append(path)
    if missing:
        raise SystemExit("gold documents not in the database: " + ", ".join(missing))

    retriever = RETRIEVERS[args.retriever]()
    outcome = run(retriever, cases, gold)
    files: list[str] = []
    for case in cases:
        if case.file not in files:
            files.append(case.file)
    saved = save(
        ran_at,
        {
            "ran_at": ran_at.isoformat(timespec="seconds"),
            "input": {"commit": commit(), "retriever": args.retriever, "cases": files},
            "result": outcome,
        },
    )
    print(json.dumps(outcome["summary"]))
    print(saved)


def resolve(paths: list[str]) -> dict[str, set[int]]:
    """Maps each case path (invoice/17.pdf) to the documents read from processed/invoice/17.pdf."""
    by_destination: dict[str, str] = {}
    for path in paths:
        by_destination["processed/" + path] = path

    gold: dict[str, set[int]] = {}
    with Session() as session:
        rows = session.execute(
            select(Ingestion.destination_path, Document.id)
            .join(Document, Document.ingestion_id == Ingestion.id)
            .where(Ingestion.destination_path.in_(list(by_destination)))
        )
        for destination, document_id in rows:
            if destination is None:
                continue
            path = by_destination[destination]
            gold.setdefault(path, set()).add(document_id)
    return gold


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
