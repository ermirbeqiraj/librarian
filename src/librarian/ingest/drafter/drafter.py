from dataclasses import dataclass
from pathlib import Path

from librarian.adapters.mistral import MAX_RETRIES, MODEL, ask, structured
from librarian.adapters.readers.element import Element
from librarian.ingest.drafter.checks import Problem, problems
from librarian.ingest.drafter.schema import Draft

INSTRUCTIONS_DIR = Path(__file__).parent / "instructions"
INSTRUCTIONS = "v4"


@dataclass(frozen=True)
class Attempt:
    draft: Draft
    problems: list[Problem]


@dataclass(frozen=True)
class CheckedDraft:
    attempts: list[Attempt]

    @property
    def draft(self) -> Draft:
        return self.attempts[-1].draft

    @property
    def problems(self) -> list[Problem]:
        return self.attempts[-1].problems


def document_text(elements: list[Element]) -> str:
    return "\n\n".join(e.text for e in elements if e.layer == "body")


def instructions_text(version: str) -> str:
    return (INSTRUCTIONS_DIR / f"{version}.md").read_text().strip()


def draft(
    text: str,
    model_name: str = MODEL,
    instructions: str = INSTRUCTIONS,
    max_retries: int = MAX_RETRIES,
) -> CheckedDraft:
    model = structured(Draft, model_name)
    messages = [("system", instructions_text(instructions)), ("human", text)]
    result = ask(model, Draft, messages, max_retries)
    found = problems(result, text)
    attempts = [Attempt(result, found)]
    while found and len(attempts) <= max_retries:
        messages.append(("ai", result.model_dump_json()))
        messages.append(("human", _feedback(found)))
        result = ask(model, Draft, messages, max_retries)
        found = problems(result, text)
        attempts.append(Attempt(result, found))
    return CheckedDraft(attempts)


def _feedback(found: list[Problem]) -> str:
    lines = ["Your draft has these problems:"]
    for problem in found:
        lines.append(f"- {problem.field}: {problem.message}")
    lines.append("Fix them and return the whole draft again.")
    return "\n".join(lines)
