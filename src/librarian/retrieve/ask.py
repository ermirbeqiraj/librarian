"""One question in, one result out: refine, then the agent digs with the tools until it
submits, then code marks which values come from documents a parser read.

`ask` runs the steps in order. Each step reads the `Inquiry` and fills its own part of it.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import sqlalchemy
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_mistralai import ChatMistralAI
from pydantic import BaseModel

from librarian.config import ASKS_DIR, CONTEXT_FILE
from librarian.db import Session
from librarian.models.document import DocumentStatus
from librarian.retrieve.refine import Refined, refine
from librarian.retrieve.result import Passage, Result, Source, Status, Value
from librarian.retrieve.schema import schema
from librarian.retrieve.search import Hit, search
from librarian.retrieve.sql import SQL_TOOL_DESCRIPTION, run_sql

ROUNDS = 20
# Choosing SQL or search, and reading a question two ways, is judgment: every model reasons.
# Set here, not left to the model: GLM thinks by default, DeepSeek and Mistral do not.
REASONING_EFFORT = "high"
INSTRUCTIONS = Path(__file__).parent / "instructions" / "dig-v7.md"
LAST_ROUND = "È l'ultimo turno: chiama `submit` adesso con quello che hai trovato."


class Call(BaseModel):
    """One tool call: the arguments as the model sent them, and what went back to it."""

    tool: str
    args: dict[str, Any]
    output: Any


class Round(BaseModel):
    """One model call of the agent: what it thought, what it wrote, the tools it called."""

    thinking: str = ""
    text: str = ""
    calls: list[Call] = []


class Inquiry(BaseModel):
    """Everything one question goes through, from the question as typed to what leaves."""

    # When it started, plus a random suffix: sorts by time, unique within a second.
    id: str
    # The agent's model; refine pins its own.
    model: str
    reasoning_effort: str = REASONING_EFFORT
    question: str
    today: date
    refined: Refined | None = None
    # At most ROUNDS.
    rounds: list[Round] = []
    # Summed over every model call of the agent (refine not counted).
    tokens_in: int = 0
    tokens_out: int = 0
    result: Result | None = None


def ask(question: str, model: str) -> Inquiry:
    now = datetime.now()
    inquiry = Inquiry(
        id=f"{now:%Y-%m-%dT%H-%M-%S}-{uuid4().hex[:6]}",
        model=model,
        question=question,
        today=now.date(),
    )
    inquiry.refined = refine(inquiry.question, inquiry.today)
    _dig(inquiry)
    _verify(inquiry)
    _save(inquiry)
    return inquiry


def _save(inquiry: Inquiry) -> None:
    """Every run kept as ASKS_DIR/<id>.json, to read back or grep later."""
    ASKS_DIR.mkdir(parents=True, exist_ok=True)
    path = ASKS_DIR / f"{inquiry.id}.json"
    path.write_text(inquiry.model_dump_json(indent=2, by_alias=True) + "\n", encoding="utf-8")


def _dig(inquiry: Inquiry) -> None:
    """The model calls the tools in the order it judges best, at most ROUNDS times, and ends
    with `submit`; on the last round `submit` is the only tool it has."""
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
            status=status, values=values, passages=passages, sources=sources, trace_id=None
        )
        return "ok"

    tools: dict[str, BaseTool] = {"search": search_sections, "sql": sql, "submit": submit}
    for each in tools.values():
        each.handle_validation_error = str
    chat = ChatMistralAI(
        model_name=inquiry.model,
        temperature=0,
        model_kwargs={"reasoning_effort": inquiry.reasoning_effort},
    )
    model = chat.bind_tools(list(tools.values()))
    assert inquiry.refined is not None
    question = json.dumps(
        inquiry.refined.model_dump(mode="json", by_alias=True), ensure_ascii=False
    )
    messages: list[BaseMessage] = [
        SystemMessage(_instructions()),
        HumanMessage(question),
    ]
    for round in range(ROUNDS):
        if round == ROUNDS - 1:
            messages.append(HumanMessage(LAST_ROUND))
            model = chat.bind_tools([submit], tool_choice="any")
        reply = model.invoke(messages)
        messages.append(reply)
        thinking, text = _said(reply.content)
        this_round = Round(thinking=thinking, text=text)
        inquiry.rounds.append(this_round)
        if reply.usage_metadata is not None:
            inquiry.tokens_in += reply.usage_metadata["input_tokens"]
            inquiry.tokens_out += reply.usage_metadata["output_tokens"]
        for tool_call in reply.tool_calls:
            if tool_call["name"] in tools:
                message = tools[tool_call["name"]].invoke(tool_call)
            else:
                # A tool error, like bad arguments: back to the model, not a crash.
                message = ToolMessage(
                    content=f"Lo strumento {tool_call['name']} non esiste.",
                    tool_call_id=tool_call["id"],
                )
            messages.append(message)
            this_round.calls.append(
                Call(
                    tool=tool_call["name"], args=tool_call["args"], output=_parsed(message.content)
                )
            )
        if inquiry.result is not None:
            return


def _verify(inquiry: Inquiry) -> None:
    """A value is verified when its source's document is confirmed: read by a parser, not
    drafted by a model. A value whose source isn't in `sources` is not verified."""
    if inquiry.result is None:
        return
    documents: dict[int, int] = {}
    for source in inquiry.result.sources:
        documents[source.id] = source.document_id
    confirmed = _confirmed(list(documents.values()))
    for value in inquiry.result.values:
        value.verified = documents.get(value.source) in confirmed


def _confirmed(document_ids: list[int]) -> set[int]:
    if not document_ids:
        return set()
    with Session() as session:
        rows = session.execute(
            sqlalchemy.text("SELECT id FROM documents WHERE status = :status AND id = ANY(:ids)"),
            {"status": DocumentStatus.confirmed.value, "ids": document_ids},
        ).all()
    confirmed: set[int] = set()
    for row in rows:
        confirmed.add(row[0])
    return confirmed


LIBRARY_SQL = """SELECT kind, fields ->> 'issuer' AS issuer, count(*) AS documents,
       min(lower(validity)) AS first, max(upper(validity)) AS last
FROM documents GROUP BY 1, 2 ORDER BY 1, 2"""


def _instructions() -> str:
    library = run_sql(LIBRARY_SQL)
    if library.error is not None:
        raise RuntimeError(f"the library query failed: {library.error}")
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    context = ""
    if CONTEXT_FILE.exists():
        context = CONTEXT_FILE.read_text(encoding="utf-8").strip()
    text = text.replace("{context}", context)
    text = text.replace("{rounds}", str(ROUNDS))
    text = text.replace("{library}", json.dumps(library.rows, ensure_ascii=False, default=str))
    return text.replace("{schema}", schema().model_dump_json(indent=1))


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
