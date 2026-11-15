from decimal import Decimal
from enum import StrEnum, auto

from pydantic import BaseModel


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
