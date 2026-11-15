"""One question in, one result out: refine, then the agent digs with the tools until it
submits, then code marks which values come from documents a parser read.

`ask` runs the steps in order. Each step fills its own part of the `Inquiry` and traces
what it did under the run's correlation id: the trace, not the `Inquiry`, is the record.
"""

import json
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import sqlalchemy
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool, tool
from langchain_mistralai import ChatMistralAI
from pydantic import BaseModel

from librarian.adapters import mistral
from librarian.config import CONTEXT_FILE
from librarian.db import Session
from librarian.models.document import DocumentStatus
from librarian.retrieve.refine import INSTRUCTIONS as REFINE_INSTRUCTIONS
from librarian.retrieve.refine import MODEL as REFINE_MODEL
from librarian.retrieve.refine import Refined, refine
from librarian.retrieve.result import Passage, Result, Source, Status, Value
from librarian.retrieve.schema import schema
from librarian.retrieve.search import Hit, search
from librarian.retrieve.sql import SQL_TOOL_DESCRIPTION, run_sql
from librarian.retrieve.trace.tracer import Event, trace

ROUNDS = 20
# Choosing SQL or search, and reading a question two ways, is judgment: every model reasons.
# Set here, not left to the model: GLM thinks by default, DeepSeek and Mistral do not.
REASONING_EFFORT = "high"
INSTRUCTIONS = Path(__file__).parent / "instructions" / "dig-v7.md"
LAST_ROUND = "È l'ultimo turno: chiama `submit` adesso con quello che hai trovato."


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
    # At most ROUNDS.
    rounds: int = 0
    calls: int = 0
    ms: int = 0


def ask(question: str, model: str, correlation_id: str) -> Inquiry:
    """The caller owns the correlation id: it names the trace and is the result's trace_id."""
    started = time.monotonic()
    today = date.today()
    trace(
        correlation_id,
        Event(
            step="started",
            kind="started",
            data={
                "question": question,
                "today": today.isoformat(),
                "git_sha": git_sha(),
                "agent_model": model,
                "reasoning": REASONING_EFFORT,
                "refine_model": REFINE_MODEL,
                "prompt": INSTRUCTIONS.name,
                "refine_prompt": REFINE_INSTRUCTIONS.name,
                "round_cap": ROUNDS,
            },
        ),
    )
    inquiry = Inquiry(correlation_id=correlation_id, question=question)
    step = "refine"
    try:
        inquiry.refined = _refine(inquiry, today)
        step = "system"
        system = _instructions(correlation_id)
        step = "round"
        _dig(inquiry, model, system)
        step = "verified"
        _verify(inquiry)
    except Exception as error:
        inquiry.ms = _ms(started)
        failed = _totals(inquiry)
        failed["error"] = f"{type(error).__name__}: {error}"
        failed["step"] = step
        if step == "round":
            failed["round"] = inquiry.rounds
        trace(correlation_id, Event(step="failed", kind="failed", ms=inquiry.ms, data=failed))
        raise
    inquiry.ms = _ms(started)
    finished = _totals(inquiry)
    finished["status"] = None
    if inquiry.result is not None:
        finished["status"] = inquiry.result.status
    trace(correlation_id, Event(step="finished", kind="finished", ms=inquiry.ms, data=finished))
    return inquiry


def _totals(inquiry: Inquiry) -> dict[str, Any]:
    return {
        "input_tokens": inquiry.tokens_in,
        "output_tokens": inquiry.tokens_out,
        "rounds": inquiry.rounds,
        "calls": inquiry.calls,
    }


def _refine(inquiry: Inquiry, today: date) -> Refined:
    """`refine` on the question, its model's tokens counted for the trace."""
    usage = {"input_tokens": 0, "output_tokens": 0}
    structured = mistral.structured(Refined, REFINE_MODEL)

    def counted(messages: Any) -> Any:
        answer = structured.invoke(messages)
        raw = answer["raw"]
        if isinstance(raw, AIMessage) and raw.usage_metadata is not None:
            usage["input_tokens"] += raw.usage_metadata["input_tokens"]
            usage["output_tokens"] += raw.usage_metadata["output_tokens"]
        return answer

    started = time.monotonic()
    refined = refine(inquiry.question, today, model=RunnableLambda(counted))
    data: dict[str, Any] = {
        "model": REFINE_MODEL,
        "input": inquiry.question,
        "output": refined.model_dump(mode="json", by_alias=True)["queries"],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
    }
    trace(inquiry.correlation_id, Event(step="refine", kind="refine", ms=_ms(started), data=data))
    return refined


def _dig(inquiry: Inquiry, model: str, system: str) -> None:
    """The model calls the tools in the order it judges best, at most ROUNDS times, and ends
    with `submit`; on the last round `submit` is the only tool it has."""
    correlation_id = inquiry.correlation_id
    seen: list[int] = []

    @tool("search")
    def search_sections(query: str, document_ids: list[int] | None = None) -> str:
        """Cerca nei testi dei documenti. Restituisce le 5 sezioni migliori, ognuna col suo
        documento. Con `document_ids` cerca solo dentro quei documenti."""
        output: list[dict[str, Any]] = []
        for hit in search(query, document_ids=document_ids, seen=seen):
            if not hit.is_ref:
                seen.append(hit.section_id)
            output.append(_hit(hit))
        return json.dumps(output, ensure_ascii=False)

    @tool("sql", description=SQL_TOOL_DESCRIPTION)
    def sql(query: str) -> str:
        return run_sql(query).model_dump_json()

    @tool
    def submit(
        status: Status, values: list[Value], passages: list[Passage], sources: list[Source]
    ) -> str:
        """Consegna il risultato. È l'ultima chiamata."""
        inquiry.result = Result(
            status=status,
            values=values,
            passages=passages,
            sources=sources,
            trace_id=correlation_id,
        )
        return "ok"

    tools: dict[str, BaseTool] = {"search": search_sections, "sql": sql, "submit": submit}
    for each in tools.values():
        each.handle_validation_error = str
    chat = ChatMistralAI(
        model_name=model,
        temperature=0,
        model_kwargs={"reasoning_effort": REASONING_EFFORT},
    )
    agent = chat.bind_tools(list(tools.values()))
    assert inquiry.refined is not None
    question = json.dumps(
        inquiry.refined.model_dump(mode="json", by_alias=True), ensure_ascii=False
    )
    trace(correlation_id, Event(step="case", kind="case", data={"message": question}))
    messages: list[BaseMessage] = [
        SystemMessage(system),
        HumanMessage(question),
    ]
    for round in range(1, ROUNDS + 1):
        if round == ROUNDS:
            messages.append(HumanMessage(LAST_ROUND))
            trace(correlation_id, Event(step="nudge", kind="nudge", data={"message": LAST_ROUND}))
            agent = chat.bind_tools([submit], tool_choice="any")
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
            _trace_round(correlation_id, round, "thinking", {"text": thinking})
        if text:
            _trace_round(correlation_id, round, "text", {"text": text})
        _trace_round(correlation_id, round, "usage", usage, _ms(started))
        for tool_call in reply.tool_calls:
            inquiry.calls += 1
            name = tool_call["name"]
            arguments = {"id": tool_call["id"], "name": name, "arguments": tool_call["args"]}
            _trace_round(correlation_id, round, "tool_call", arguments)
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
            _trace_round(correlation_id, round, "tool_result", result, _ms(started))
        if inquiry.result is not None:
            submitted = inquiry.result.model_dump(mode="json")
            trace(correlation_id, Event(step="submitted", kind="submitted", data=submitted))
            return


def _trace_round(
    correlation_id: str, round: int, kind: str, data: dict[str, Any], ms: int | None = None
) -> None:
    trace(correlation_id, Event(step="round", round=round, kind=kind, ms=ms, data=data))


def _verify(inquiry: Inquiry) -> None:
    """A value is verified when its source's document is confirmed: read by a parser, not
    drafted by a model. A value whose source isn't in `sources` is not verified."""
    if inquiry.result is None:
        return
    documents: dict[int, int] = {}
    for source in inquiry.result.sources:
        documents[source.id] = source.document_id
    statuses = _statuses(list(documents.values()))
    marked: list[dict[str, Any]] = []
    for value in inquiry.result.values:
        document_id = documents.get(value.source)
        status = None
        if document_id is not None:
            status = statuses.get(document_id)
        value.verified = status == DocumentStatus.confirmed
        marked.append(
            {
                "name": value.name,
                "source": value.source,
                "document_id": document_id,
                "document_status": status,
                "verified": value.verified,
            }
        )
    trace(
        inquiry.correlation_id,
        Event(step="verified", kind="verified", data={"values": marked}),
    )


def _statuses(document_ids: list[int]) -> dict[int, str]:
    statuses: dict[int, str] = {}
    if not document_ids:
        return statuses
    with Session() as session:
        rows = session.execute(
            sqlalchemy.text("SELECT id, status FROM documents WHERE id = ANY(:ids)"),
            {"ids": document_ids},
        ).all()
    for row in rows:
        statuses[row[0]] = row[1]
    return statuses


def git_sha() -> str | None:
    """The commit this code runs from, -dirty with uncommitted changes; None when git
    can't answer (the image has no git and no .git)."""
    here = Path(__file__).parent
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=here,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        changes = subprocess.run(
            ["git", "status", "--porcelain"], cwd=here, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if changes:
        return head + "-dirty"
    return head


def _ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


LIBRARY_SQL = """SELECT kind, fields ->> 'issuer' AS issuer, count(*) AS documents,
       min(lower(validity)) AS first, max(upper(validity)) AS last
FROM documents GROUP BY 1, 2 ORDER BY 1, 2"""


def _instructions(correlation_id: str) -> str:
    library = run_sql(LIBRARY_SQL)
    if library.error is not None:
        raise RuntimeError(f"the library query failed: {library.error}")
    rows = json.dumps(library.rows, ensure_ascii=False, default=str)
    library_schema = schema()
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    context = ""
    if CONTEXT_FILE.exists():
        context = CONTEXT_FILE.read_text(encoding="utf-8").strip()
    text = text.replace("{context}", context)
    text = text.replace("{rounds}", str(ROUNDS))
    text = text.replace("{library}", rows)
    text = text.replace("{schema}", library_schema.model_dump_json(indent=1))
    data = {
        "prompt": INSTRUCTIONS.name,
        "context": context,
        "library": json.loads(rows),
        "schema": library_schema.model_dump(mode="json"),
        "text": text,
    }
    trace(correlation_id, Event(step="system", kind="system", data=data))
    return text


def _hit(hit: Hit) -> dict[str, Any]:
    if hit.is_ref:
        return {"section_id": hit.section_id, "already_returned": True}
    valid: dict[str, str | None] | None = None
    if hit.validity is not None:
        # Inclusive, like the periods refine gives.
        end = hit.validity.upper
        if end is not None and not hit.validity.upper_inc:
            end = end - timedelta(days=1)
        valid = {
            "from": str(hit.validity.lower) if hit.validity.lower else None,
            "to": str(end) if end else None,
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
