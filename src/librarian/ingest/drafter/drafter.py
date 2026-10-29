import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_mistralai import ChatMistralAI

from librarian.adapters.readers.element import Element
from librarian.ingest.drafter.checks import Problem, problems
from librarian.ingest.drafter.schema import Draft

MODEL = "mistral-small-latest"
MAX_RETRIES = 5

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
    model = ChatMistralAI(model_name=model_name, temperature=0).with_structured_output(
        Draft, include_raw=True
    )
    messages = [("system", instructions_text(instructions)), ("human", text)]
    result = _ask(model, messages, max_retries)
    found = problems(result, text)
    attempts = [Attempt(result, found)]
    while found and len(attempts) <= max_retries:
        messages.append(("ai", result.model_dump_json()))
        messages.append(("human", _feedback(found)))
        result = _ask(model, messages, max_retries)
        found = problems(result, text)
        attempts.append(Attempt(result, found))
    return CheckedDraft(attempts)


def _ask(model: Runnable[Any, Any], messages: list[tuple[str, str]], max_retries: int) -> Draft:
    """Asks again while the answer doesn't fit the schema, then raises its error."""
    asked = list(messages)
    result = model.invoke(asked)
    for _ in range(max_retries):
        if result["parsing_error"] is None and isinstance(result["parsed"], Draft):
            break
        asked.append(("ai", _answer(result["raw"])))
        asked.append(("human", _invalid(result["parsing_error"])))
        result = model.invoke(asked)
    if result["parsing_error"] is not None:
        raise result["parsing_error"]
    parsed = result["parsed"]
    if not isinstance(parsed, Draft):
        raise TypeError(f"expected a Draft, got {type(parsed).__name__}")
    return parsed


def _answer(raw: BaseMessage) -> str:
    if isinstance(raw, AIMessage) and raw.tool_calls:
        return json.dumps(raw.tool_calls[0]["args"], ensure_ascii=False)
    return str(raw.content)


def _invalid(error: BaseException | None) -> str:
    if error is None:
        return "Your answer has no draft. Return the whole draft."
    return f"Your draft does not fit the schema:\n{error}\nFix it and return the whole draft again."


def _feedback(found: list[Problem]) -> str:
    lines = ["Your draft has these problems:"]
    for problem in found:
        lines.append(f"- {problem.field}: {problem.message}")
    lines.append("Fix them and return the whole draft again.")
    return "\n".join(lines)
