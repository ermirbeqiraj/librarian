"""Refine a question before retrieval: one model call that corrects the text, splits it
when it is really several questions, and turns each one's time words into exact dates,
worked out from a given today.

No database, no document data: a string goes in, JSON comes out. Everything else in the
question (provider, kind of document, "l'ultima", "adesso") stays in the corrected text
for the caller to read.
"""

from datetime import date
from pathlib import Path
from typing import Any

from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict, Field, model_validator

from librarian.adapters import mistral

# Medium, not small: with the same prompt (v3), small kept missing a few cases that are date
# arithmetic, not rules: a month without a year put in last year, "l'estate scorsa" a year
# too early, two months far apart merged into one period. Medium gets them all. Pinned to a
# dated version (what mistral-medium-latest pointed to on 2026-11-12) so an alias update
# can't move the score.
MODEL = "mistral-medium-2604"
MAX_RETRIES = mistral.MAX_RETRIES

INSTRUCTIONS_DIR = Path(__file__).parent / "instructions"
INSTRUCTIONS = "v3"

MESI = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


class QueryPeriod(BaseModel):
    """`from` and `to` as ISO dates, both inclusive; either can be null."""

    model_config = ConfigDict(populate_by_name=True)

    from_: date | None = Field(default=None, alias="from")
    to: date | None = None

    @model_validator(mode="after")
    def _from_not_after_to(self) -> "QueryPeriod":
        if self.from_ is not None and self.to is not None and self.from_ > self.to:
            raise ValueError(f"'from' {self.from_.isoformat()} is after 'to' {self.to.isoformat()}")
        return self


class Query(BaseModel):
    """One question on its own: the corrected text, and its period when it names a time."""

    text: str = Field(min_length=1)
    period: QueryPeriod | None = None


class Refined(BaseModel):
    """The answer of `refine`: the question as it came, and one or more queries."""

    model_config = ConfigDict(populate_by_name=True)

    user_query: str
    queries: list[Query] = Field(min_length=1)


def refine(
    question: str,
    today: date,
    *,
    model: Runnable[Any, Any] | None = None,
    model_name: str = MODEL,
    max_retries: int = MAX_RETRIES,
) -> Refined:
    """One model call on the question. The schema checks (valid shape, real dates,
    `from` <= `to`) are retries inside `ask`; a second failure raises its error."""
    if model is None:
        model = mistral.structured(Refined, model_name)
    messages = [("system", _instructions(today)), ("human", question)]
    refined = mistral.ask(model, Refined, messages, max_retries)
    # The question exactly as it came is guaranteed by code, not trusted to the model.
    return refined.model_copy(update={"user_query": question})


def instructions_text(version: str) -> str:
    return (INSTRUCTIONS_DIR / f"{version}.md").read_text(encoding="utf-8").strip()


def _instructions(today: date) -> str:
    oggi = f"{today.day} {MESI[today.month - 1]} {today.year}"
    return (
        instructions_text(INSTRUCTIONS)
        .replace("{today}", today.isoformat())
        .replace("{oggi}", oggi)
    )
