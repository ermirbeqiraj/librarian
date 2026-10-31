from decimal import Decimal
from enum import StrEnum, auto

from pydantic import BaseModel


class Status(StrEnum):
    found = auto()
    partial = auto()
    not_found = auto()


class Source(BaseModel):
    id: int
    document_id: int
    kind: str
    section: str | None
    page: int | None


class Value(BaseModel):
    name: str
    # A number as SQL returns it, or text as written: "63,33 €", "04/11/2026", a code.
    value: Decimal | str
    unit: str | None
    verified: bool
    source: int


class Passage(BaseModel):
    text: str
    source: int


class Result(BaseModel):
    # None only from a retriever that gave no answer at all.
    status: Status | None
    values: list[Value]
    passages: list[Passage]
    sources: list[Source]
    trace_id: str | None
