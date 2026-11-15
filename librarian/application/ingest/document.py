"""What ingest builds as a file goes through: its ingestion and the document read from it.
Plain values: the repository maps them to and from its rows."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum, auto
from typing import Any


@dataclass(frozen=True)
class Period:
    """A document's validity, both days inclusive; no end while it is open."""

    start: date
    end: date | None


class DocumentStatus(StrEnum):
    draft = auto()
    confirmed = auto()


@dataclass(frozen=True)
class Chunk:
    """An embedded piece of a section."""

    text: str
    model: str
    embedding: list[float]


@dataclass(frozen=True)
class DocumentSection:
    """A section stored whole, with the chunks search finds it by."""

    heading: str
    text: str
    chunks: list[Chunk]


@dataclass(frozen=True)
class Document:
    kind: str
    validity: Period | None
    fields: dict[str, Any]
    parser: str
    description: str | None
    problems: list[dict[str, str]]
    status: DocumentStatus
    sections: list[DocumentSection]


class IngestionStatus(StrEnum):
    received = auto()
    done = auto()
    duplicate = auto()
    failed = auto()


@dataclass
class Ingestion:
    """One file's way through, filled in as it goes; `id` comes from the repository."""

    original_file_name: str
    file_size: int
    id: int = 0
    status: IngestionStatus = IngestionStatus.received
    content_hash: str | None = None
    error: str | None = None
    destination_path: str | None = None
    document: Document | None = None
