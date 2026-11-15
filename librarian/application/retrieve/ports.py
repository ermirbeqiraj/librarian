"""Where retrieve reaches outside: each port is what an ask calls, an adapter is what answers
it, and a host hands the adapters in."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict

from librarian.application.ingest import document
from librarian.application.retrieve.period import Period


@dataclass
class Usage:
    """Tokens a model spent, summed over its calls."""

    input_tokens: int = 0
    output_tokens: int = 0


class Chat(Protocol):
    """The chat model the agent and refine call."""

    model: str

    def answer[T: BaseModel](
        self, schema: type[T], messages: list[tuple[str, str]], *, usage: Usage | None = None
    ) -> T:
        """An answer in `schema`, its tokens added to `usage`."""
        ...

    def with_tools(
        self, tools: list[BaseTool], reasoning_effort: str, tool_choice: str | None = None
    ) -> Runnable[LanguageModelInput, AIMessage]: ...


Mode = Literal["keyword", "vector", "hybrid"]


class Hit(BaseModel):
    """One returned section. A section in `seen` comes back as its id only (`is_ref`)."""

    section_id: int
    document_id: int | None = None
    kind: str | None = None
    issuer: str | None = None
    validity: document.Period | None = None
    heading: str | None = None
    text: str | None = None
    # The best chunk's text, which a long section is trimmed around.
    chunk_text: str | None = None
    verified: bool | None = None
    keyword_rank: int | None = None
    vector_rank: int | None = None

    @classmethod
    def ref(cls, section_id: int) -> "Hit":
        return cls(section_id=section_id)

    @property
    def is_ref(self) -> bool:
        return self.document_id is None


class Search(Protocol):
    def search(
        self,
        query: str,
        period: Period | None = None,
        kind: str | None = None,
        document_ids: Iterable[int] | None = None,
        limit: int = 5,
        mode: Mode = "hybrid",
    ) -> list[Hit]:
        """Whole sections, best first, each text uncut. `document_ids` empty means no hits."""
        ...


class SqlResult(BaseModel):
    """One query's outcome: `rows` (with `columns`), or the database's `error`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    error: str | None = None


class Column(BaseModel):
    name: str
    type: str


class Table(BaseModel):
    name: str
    columns: list[Column]


class FieldKey(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str
    document_count: int
    kinds: list[str]
    example: Any


class Schema(BaseModel):
    """What the agent can read: the tables with their columns, and the most used keys of
    `documents.fields`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tables: list[Table]
    field_keys: list[FieldKey]


class Sql(Protocol):
    def run_sql(self, query: str) -> SqlResult:
        """The agent's query, read-only; a bad one comes back as its error."""
        ...

    def schema(self) -> Schema: ...

    def library(self) -> SqlResult:
        """The documents by kind and issuer: how many, and the first and last day they cover."""
        ...


class Documents(Protocol):
    def section(self, section_id: int) -> str | None:
        """The section's whole text under its heading; None when there is none."""
        ...

    def document(self, document_id: int) -> str | None:
        """The document's sections in order; None when there is none."""
        ...

    def sections(self, document_id: int) -> dict[int, str] | None:
        """The document's sections by id, as `section` gives each."""
        ...

    def statuses(self, document_ids: list[int]) -> dict[int, str]: ...

    def paths(self, document_ids: list[int]) -> dict[int, str]:
        """Each document's file, under the library's root."""
        ...


class Event(BaseModel):
    """One thing a run did. The ask says step, kind and data, with `round` on round events and
    `ms` on the event that ends a step; the tracer sets seq and at."""

    seq: int = 0
    at: datetime | None = None
    step: str
    round: int | None = None
    kind: str
    ms: int | None = None
    data: dict[str, Any]


class TraceStore(Protocol):
    def write(self, correlation_id: str, events: list[Event]) -> None: ...

    def read(self, correlation_id: str) -> list[Event]: ...


class Feedback(Protocol):
    def rate(self, trace_id: str, rating: str, note: str | None, source: str) -> bool:
        """Stores a rating of a run; False when there is no such run."""
        ...
