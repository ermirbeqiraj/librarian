from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any, Protocol

from librarian.application.ingest.document import Period
from librarian.application.ingest.element import Element
from librarian.application.ingest.kinds import FIELDS, DocumentKind
from librarian.application.ingest.parsers.sections import Section


class ParseError(Exception):
    pass


class Claim(StrEnum):
    no = auto()
    provider = auto()
    full = auto()


@dataclass(frozen=True)
class Parsed:
    kind: DocumentKind
    validity: Period | None
    fields: dict[str, Any]

    def __post_init__(self) -> None:
        listed = FIELDS.get(self.kind, [])
        for name in self.fields:
            if name not in listed:
                raise ParseError(f"{name!r} is not in the {self.kind} field list")


class Parser(Protocol):
    issuer: str
    """The issuer's name, written in the document's fields under the key 'issuer'."""

    parser: str
    """This layout's name, stored in documents.parser (e.g. 'tim')."""

    def is_this_yours(self, elements: list[Element]) -> Claim: ...

    def parse(self, elements: list[Element]) -> Parsed: ...

    def sections(self, elements: list[Element]) -> list[Section]: ...


def claim(elements: list[Element], tax_id: str, headings: set[str]) -> Claim:
    if not any(tax_id in e.text for e in elements):
        return Claim.no
    if headings <= {e.text for e in elements}:
        return Claim.full
    return Claim.provider
