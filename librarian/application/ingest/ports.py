"""Where ingest reaches outside: each port is what the pipeline calls, an adapter is what
answers it, and a host hands the adapters in."""

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from librarian.application.ingest.document import Ingestion
from librarian.application.ingest.element import Element
from librarian.application.ingest.paid_calls import PaidCalls


class Reader(Protocol):
    """A file in, its elements out. A paid reader spends from the document's paid calls."""

    def read(self, path: Path, paid_calls: PaidCalls | None = None) -> list[Element]: ...


class Llm(Protocol):
    """A prompt and a schema in, an answer in that schema out."""

    def answer[T: BaseModel](
        self,
        schema: type[T],
        messages: list[tuple[str, str]],
        *,
        paid_calls: PaidCalls | None = None,
    ) -> T: ...


class Embedder(Protocol):
    model: str
    """The name each chunk is stored with."""

    budget: int
    """The tokens one chunk may hold."""

    def count_tokens(self, text: str) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class IngestionRepository(Protocol):
    def start(self, ingestion: Ingestion) -> int:
        """Writes the received row; its id names the file."""
        ...

    def is_duplicate(self, content_hash: str) -> bool:
        """True when a file with this content was already read."""
        ...

    def finish(self, ingestion: Ingestion) -> None:
        """Writes how it ended: done with its document, duplicate, or failed."""
        ...


class Inbox(Protocol):
    def files(self) -> list[Path]:
        """What waits in the inbox, by name."""
        ...

    def settled(self, path: Path) -> bool:
        """True when the file is no longer being written."""
        ...

    def size(self, path: Path) -> int: ...

    def move(self, path: Path, ingestion_id: int, kind: str | None) -> str:
        """To processed/ under its kind, or to quarantine/ without one; returns where it went,
        as the row stores it."""
        ...

    def move_back(self, destination: str, path: Path) -> None: ...

    def delete(self, path: Path) -> None: ...
