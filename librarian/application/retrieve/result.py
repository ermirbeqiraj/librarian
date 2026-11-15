from decimal import Decimal
from enum import StrEnum, auto

from pydantic import BaseModel

from librarian.application.retrieve.refine import Refined


class Status(StrEnum):
    found = auto()
    partial = auto()
    not_found = auto()


class Source(BaseModel):
    """A source as the agent submits it."""

    id: int
    document_id: int
    kind: str
    section: str | None
    # The section's id from a search hit; None when the source is a row from sql.
    section_id: int | None


class LinkedSource(Source):
    """A source as the result gives it. Set by code after the agent submits: the lengths of
    what get_section and get_document return, and a link to the document's file."""

    section_chars: int | None = None
    document_chars: int | None = None
    file: str | None = None


class Value(BaseModel):
    name: str
    # A number as SQL returns it, or text as written: "63,33 €", "04/11/2026", a code.
    value: Decimal | str
    unit: str | None
    # Set by code after the agent submits, whatever the agent sent: true only when the
    # source's document was read by a parser (confirmed), not drafted by a model.
    verified: bool = False
    source: int


class Passage(BaseModel):
    text: str
    source: int


class Result(BaseModel):
    # None only when the agent never submitted.
    status: Status | None
    values: list[Value]
    passages: list[Passage]
    sources: list[LinkedSource]
    trace_id: str | None


class Inquiry(BaseModel):
    """What one ask hands back: the question, its refined queries, the result, and the
    totals the eval prints. Every step it went through is in its trace."""

    correlation_id: str
    question: str
    refined: Refined | None = None
    result: Result | None = None
    # Summed over every model call of the agent; refine's are in its own event.
    tokens_in: int = 0
    tokens_out: int = 0
    # At most the agent's ROUNDS.
    rounds: int = 0
    calls: int = 0
    ms: int = 0
