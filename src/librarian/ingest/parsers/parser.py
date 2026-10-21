from dataclasses import dataclass
from datetime import date
from enum import StrEnum, auto
from typing import Any, Protocol

from sqlalchemy.dialects.postgresql import Range

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.sections import Section
from librarian.models.document_kind import DocumentKind


class ParseError(Exception):
    pass


class Claim(StrEnum):
    no = auto()
    provider = auto()
    full = auto()


@dataclass(frozen=True)
class Parsed:
    kind: DocumentKind
    validity: Range[date] | None
    fields: dict[str, Any]


class Parser(Protocol):
    def is_this_yours(self, elements: list[Element]) -> Claim: ...

    def parse(self, elements: list[Element]) -> Parsed: ...

    def sections(self, elements: list[Element]) -> list[Section]: ...


def claim(elements: list[Element], tax_id: str, headings: set[str]) -> Claim:
    if not any(tax_id in e.text for e in elements):
        return Claim.no
    if headings <= {e.text for e in elements}:
        return Claim.full
    return Claim.provider
