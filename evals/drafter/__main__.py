"""Drafts every case in evals/drafter/ (a case names its PDF, reader, model, prompt and
retries) and scores the kind, the validity and the fields against the case's expected ones.
Each run writes runs/<time> <case>.json with the prompt, the text and every attempt."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from librarian.adapters.docling import Docling
from librarian.adapters.mistral import Mistral
from librarian.adapters.ocr import MistralOcr
from librarian.application.ingest.drafter.drafter import (
    CheckedDraft,
    document_text,
    draft,
    instructions_text,
)
from librarian.hosts import config
from librarian.hosts.git import git_sha

CASES_DIR = config.ROOT / "evals" / "drafter"
RUNS_DIR = CASES_DIR / "runs"


def main() -> None:
    for case_path in sorted(CASES_DIR.glob("*.json")):
        case = json.loads(case_path.read_text())
        pipeline = case["pipeline"]
        text = load_text(case_path, case_path.parent / case["pdf"], pipeline["reader"])
        ran_at = datetime.now()
        llm = Mistral(pipeline["model"], pipeline["max_retries"])
        checked = draft(text, llm, pipeline["instructions"], pipeline["max_retries"])
        run = {
            "ran_at": ran_at.isoformat(timespec="seconds"),
            "input": {
                "case": case,
                "instructions": instructions_text(pipeline["instructions"]),
                "document": text,
                "commit": git_sha(),
            },
            "result": {
                "scores": scores(case["expected"], checked),
                "attempts": attempts(checked),
            },
        }
        save(ran_at, case_path.stem, run)
        print(
            f"{run['ran_at']} {case_path.stem} {pipeline['instructions']} {run['result']['scores']}"
        )


def load_text(case_path: Path, pdf: Path, reader: str) -> str:
    cache = case_path.with_name(f"{case_path.stem}.{reader}.txt")
    if cache.exists():
        return cache.read_text()
    if reader == "docling":
        text = document_text(Docling(config.DOCLING_URL).read(pdf))
    elif reader == "mistral-ocr":
        pages: list[str] = []
        for page in MistralOcr().read(pdf):
            pages.append(page.text)
        text = "\n\n".join(pages)
    else:
        raise ValueError(f"unknown reader {reader!r}")
    cache.write_text(text)
    return text


def scores(expected: dict[str, Any], checked: CheckedDraft) -> dict[str, Any]:
    validity = checked.draft.validity
    end = None
    if validity.end is not None:
        end = validity.end.isoformat()
    return {
        "kind": checked.draft.kind == expected["kind"],
        "validity": validity.start.isoformat() == expected["validity"]["start"]
        and end == expected["validity"]["end"],
        "fields": len(checked.draft.fields),
        "expected_fields": expected["fields"],
        "attempts": len(checked.attempts),
        "problems": len(checked.problems),
    }


def attempts(checked: CheckedDraft) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for attempt in checked.attempts:
        problems: list[dict[str, str]] = []
        for problem in attempt.problems:
            problems.append(asdict(problem))
        result.append({"draft": attempt.draft.model_dump(mode="json"), "problems": problems})
    return result


def save(ran_at: datetime, case: str, run: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{ran_at:%Y-%m-%dT%H-%M-%S} {case}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
