"""The agent loop: the model calls the tools in the order it judges best, at most ROUNDS
times, and ends with `submit`; on the last round `submit` is the only tool it has. Every
round's thinking, text, tool calls and results go to the trace."""

import json
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool

from librarian.application.retrieve.ports import Chat, Event, Hit, Search, Sql
from librarian.application.retrieve.result import (
    Inquiry,
    LinkedSource,
    Passage,
    Result,
    Source,
    Status,
    Value,
)
from librarian.application.retrieve.search import search
from librarian.application.retrieve.tracer import Tracer

ROUNDS = 20
# Choosing SQL or search, and reading a question two ways, is judgment: every model reasons.
# Set here, not left to the model: GLM thinks by default, DeepSeek and Mistral do not.
REASONING_EFFORT = "high"
INSTRUCTIONS = Path(__file__).parent / "instructions" / "dig-v8.md"
LAST_ROUND = "È l'ultimo turno: chiama `submit` adesso con quello che hai trovato."

EXAMPLES: list[str] = [
    # Check the connection.
    "SELECT 1",
    # Count documents per kind.
    """SELECT kind, count(*) AS documents
FROM documents
GROUP BY kind
ORDER BY documents DESC""",
    # The latest gas bill and its total.
    """SELECT id, validity, fields ->> 'total_amount' AS total_amount
FROM documents
WHERE kind = 'invoice' AND fields ->> 'service' = 'gas'
ORDER BY lower(validity) DESC
LIMIT 1""",
    # Water spent in 2025: a sum over a date range on validity.
    """SELECT sum((fields ->> 'total_amount')::numeric) AS spent_2025
FROM documents
WHERE fields ->> 'service' = 'water'
  AND validity && daterange('2025-01-01', '2026-01-01', '[)')""",
    # One value out of `fields`, cast to a number.
    """SELECT id, (fields ->> 'total_amount')::numeric AS total_amount
FROM documents
WHERE fields ? 'total_amount'
ORDER BY lower(validity) DESC
LIMIT 10""",
]

_EXAMPLES_SQL = "\n\n".join(f"```sql\n{example}\n```" for example in EXAMPLES)

SQL_TOOL_DESCRIPTION = f"""Run one SQL query against the library database and read the rows.

What you can see (the columns and the most used `fields` keys are in your instructions):
- documents(id, ingestion_id, kind, validity, fields, parser, description, problems, status, created_at)
- document_sections(id, document_id, position, heading, text, created_at)

`fields` is a JSON object: its keys are not columns. Read a value with fields ->> 'key',
test for a key with fields ? 'key'. `validity` is a date range stored as [start, end):
lower(validity) is the first day, upper(validity) the day after the last one. In the
rows it comes back as {{start, end}} with end the last day. validity &&
daterange('2025-01-01', '2026-01-01') matches the year 2025.

Only a query runs: SELECT, WITH ... SELECT, VALUES or TABLE. Writes, SET, SHOW and
EXPLAIN fail at the database.

Limits: the connection is read-only, writes fail at the database; each statement stops
after 5 seconds; a query returning more than 200 rows is an error, aggregate in SQL or
add a LIMIT.

Examples, from simple to hard:

{_EXAMPLES_SQL}
"""


def dig(
    inquiry: Inquiry, chat: Chat, sections: Search, sql: Sql, tracer: Tracer, system: str
) -> None:
    correlation_id = inquiry.correlation_id
    seen: list[int] = []

    @tool("search")
    def search_sections(query: str, document_ids: list[int] | None = None) -> str:
        """Cerca nei testi dei documenti. Restituisce le 5 sezioni migliori, ognuna col suo
        documento. Con `document_ids` cerca solo dentro quei documenti."""
        output: list[dict[str, Any]] = []
        for hit in search(sections, query, document_ids=document_ids, seen=seen):
            if not hit.is_ref:
                seen.append(hit.section_id)
            output.append(_hit(hit))
        return json.dumps(output, ensure_ascii=False)

    @tool("sql", description=SQL_TOOL_DESCRIPTION)
    def run_sql(query: str) -> str:
        return sql.run_sql(query).model_dump_json()

    @tool
    def submit(
        status: Status, values: list[Value], passages: list[Passage], sources: list[Source]
    ) -> str:
        """Consegna il risultato. È l'ultima chiamata."""
        linked: list[LinkedSource] = []
        for source in sources:
            linked.append(LinkedSource.model_validate(source.model_dump()))
        inquiry.result = Result(
            status=status,
            values=values,
            passages=passages,
            sources=linked,
            trace_id=correlation_id,
        )
        return "ok"

    tools: dict[str, BaseTool] = {"search": search_sections, "sql": run_sql, "submit": submit}
    for each in tools.values():
        each.handle_validation_error = str
    agent = chat.with_tools(list(tools.values()), REASONING_EFFORT)
    assert inquiry.refined is not None
    question = json.dumps(
        inquiry.refined.model_dump(mode="json", by_alias=True), ensure_ascii=False
    )
    tracer.trace(correlation_id, Event(step="case", kind="case", data={"message": question}))
    messages: list[BaseMessage] = [
        SystemMessage(system),
        HumanMessage(question),
    ]
    for round in range(1, ROUNDS + 1):
        if round == ROUNDS:
            messages.append(HumanMessage(LAST_ROUND))
            nudge = Event(step="nudge", kind="nudge", data={"message": LAST_ROUND})
            tracer.trace(correlation_id, nudge)
            agent = chat.with_tools([submit], REASONING_EFFORT, tool_choice="any")
        inquiry.rounds = round
        started = time.monotonic()
        reply = agent.invoke(messages)
        usage = {"input_tokens": 0, "output_tokens": 0}
        if reply.usage_metadata is not None:
            usage["input_tokens"] = reply.usage_metadata["input_tokens"]
            usage["output_tokens"] = reply.usage_metadata["output_tokens"]
        inquiry.tokens_in += usage["input_tokens"]
        inquiry.tokens_out += usage["output_tokens"]
        messages.append(reply)
        thinking, text = _said(reply.content)
        if thinking:
            _trace_round(tracer, correlation_id, round, "thinking", {"text": thinking})
        if text:
            _trace_round(tracer, correlation_id, round, "text", {"text": text})
        _trace_round(tracer, correlation_id, round, "usage", usage, ms(started))
        for tool_call in reply.tool_calls:
            inquiry.calls += 1
            name = tool_call["name"]
            arguments = {"id": tool_call["id"], "name": name, "arguments": tool_call["args"]}
            _trace_round(tracer, correlation_id, round, "tool_call", arguments)
            started = time.monotonic()
            if name in tools:
                message = tools[name].invoke(tool_call)
            else:
                # A tool error, like bad arguments: back to the model, not a crash.
                message = ToolMessage(
                    content=f"Lo strumento {name} non esiste.",
                    tool_call_id=tool_call["id"],
                    status="error",
                )
            messages.append(message)
            output = _parsed(message.content)
            error = None
            if message.status == "error":
                error = message.content
            elif name == "sql":
                error = output["error"]
            result = {"id": tool_call["id"], "name": name, "output": output, "error": error}
            _trace_round(tracer, correlation_id, round, "tool_result", result, ms(started))
        if inquiry.result is not None:
            submitted = inquiry.result.model_dump(mode="json")
            tracer.trace(correlation_id, Event(step="submitted", kind="submitted", data=submitted))
            return


def ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _trace_round(
    tracer: Tracer,
    correlation_id: str,
    round: int,
    kind: str,
    data: dict[str, Any],
    ms: int | None = None,
) -> None:
    tracer.trace(correlation_id, Event(step="round", round=round, kind=kind, ms=ms, data=data))


def _hit(hit: Hit) -> dict[str, Any]:
    if hit.is_ref:
        return {"section_id": hit.section_id, "already_returned": True}
    valid: dict[str, str | None] | None = None
    if hit.validity is not None:
        # Inclusive, like the periods refine gives.
        valid = {
            "from": str(hit.validity.start) if hit.validity.start else None,
            "to": str(hit.validity.end) if hit.validity.end else None,
        }
    return {
        "section_id": hit.section_id,
        "document_id": hit.document_id,
        "kind": hit.kind,
        "issuer": hit.issuer,
        "validity": valid,
        "heading": hit.heading,
        "text": hit.text,
        "verified": hit.verified,
    }


def _said(content: str | list[Any]) -> tuple[str, str]:
    """The reply's thinking and its text. Content is a string, or blocks when the model thinks."""
    if isinstance(content, str):
        return "", content
    thinking: list[str] = []
    text: list[str] = []
    for block in content:
        if isinstance(block, str):
            text.append(block)
        elif block.get("type") == "thinking":
            for part in block["thinking"]:
                thinking.append(part.get("text", ""))
        elif block.get("type") == "text":
            text.append(block["text"])
    return "".join(thinking), "".join(text)


def _parsed(content: Any) -> Any:
    """What the tool sent back, as JSON when it is JSON: easier to read in the dump."""
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return content
