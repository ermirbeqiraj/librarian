"""Every outside call of an ask, faked: the chat follows a script, the rest answers empty."""

from typing import Any

from langchain_core.messages import AIMessage

from librarian.application.retrieve.ask import Asker
from librarian.application.retrieve.ports import Event, Schema, SqlResult, Usage
from librarian.application.retrieve.refine import Query, Refined

USAGE = {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
SEARCH = {"name": "search", "args": {"query": "bolletta"}}
SUBMIT = {
    "name": "submit",
    "args": {"status": "not_found", "values": [], "passages": [], "sources": []},
}


class FakeChat:
    """The agent: answers each round with the next tool call of a script; past its end,
    repeats the last. A script entry that is an exception is raised instead. As refine, it
    corrects every question to the same query."""

    model = "fake"

    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.round = 0

    def with_tools(
        self, tools: list[Any], reasoning_effort: str, tool_choice: str | None = None
    ) -> "FakeChat":
        return self

    def invoke(self, messages: list[Any]) -> AIMessage:
        call = self.script[min(self.round, len(self.script) - 1)]
        self.round += 1
        if isinstance(call, Exception):
            raise call
        thinking = {
            "type": "thinking",
            "thinking": [{"type": "text", "text": f"step {self.round}"}],
        }
        return AIMessage(
            content=[thinking],
            tool_calls=[{**call, "id": f"call-{self.round}"}],
            usage_metadata=USAGE,
        )

    def answer(self, schema: Any, messages: Any, *, usage: Usage | None = None) -> Refined:
        if usage is not None:
            usage.input_tokens += USAGE["input_tokens"]
            usage.output_tokens += USAGE["output_tokens"]
        return Refined(user_query="q", queries=[Query(text="bolletta corretta")])


class FakeSql:
    def run_sql(self, query: str) -> SqlResult:
        if "boom" in query:
            return SqlResult(error='syntax error at or near "boom"')
        # A float: Postgres gives it back as a Decimal.
        return SqlResult(columns=["share"], rows=[{"share": 0.5}])

    def schema(self) -> Schema:
        return Schema(tables=[], field_keys=[])

    def library(self) -> SqlResult:
        return SqlResult(columns=[], rows=[])


class NoSearch:
    def search(self, query: str, *args: Any) -> list[Any]:
        return []


class NoDocuments:
    def __init__(self, statuses: dict[int, str] | None = None) -> None:
        self.statuses_by_id = statuses or {}

    def section(self, section_id: int) -> None:
        return None

    def document(self, document_id: int) -> None:
        return None

    def sections(self, document_id: int) -> None:
        return None

    def statuses(self, document_ids: list[int]) -> dict[int, str]:
        return self.statuses_by_id

    def paths(self, document_ids: list[int]) -> dict[int, str]:
        return {}


class Recorder:
    """A tracer that keeps every event in a list."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def trace(self, correlation_id: str, event: Event) -> None:
        self.events.append(event)


def asker(
    tracer: Any,
    script: list[Any] = (),
    documents: Any = None,
    context: str = "",
) -> Asker:
    """An ask with every outside call faked; the agent follows `script`."""
    return Asker(
        agent_chat=FakeChat(list(script)),
        refine_chat=FakeChat([]),
        search=NoSearch(),
        sql=FakeSql(),
        documents=documents or NoDocuments(),
        tracer=tracer,
        context=lambda: context,
        file_url=None,
        git_sha=None,
    )
