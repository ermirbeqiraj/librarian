import json
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from librarian.adapters.readers import docling_reader, mistral_ocr
from librarian.ingest.drafter.drafter import CheckedDraft, document_text, draft, instructions_text

CASES_DIR = Path.home() / "Dropbox" / "library" / "evals" / "drafter"
RUNS_DIR = Path.home() / "Dropbox" / "library" / "learnings" / "evals" / "drafter"


def main() -> None:
    for case_path in sorted(CASES_DIR.glob("*.json")):
        case = json.loads(case_path.read_text())
        pipeline = case["pipeline"]
        text = load_text(case_path, case_path.parent / case["pdf"], pipeline["reader"])
        ran_at = datetime.now()
        checked = draft(text, pipeline["model"], pipeline["instructions"], pipeline["max_retries"])
        run = {
            "ran_at": ran_at.isoformat(timespec="seconds"),
            "input": {
                "case": case,
                "instructions": instructions_text(pipeline["instructions"]),
                "document": text,
                "commit": commit(),
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
        text = document_text(docling_reader.read(pdf))
    elif reader == "mistral-ocr":
        text = mistral_ocr.read_text(pdf)
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


def save(ran_at: datetime, case: str, run: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{ran_at:%Y-%m-%dT%H-%M-%S} {case}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
