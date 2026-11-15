"""The outside agent's way in: an MCP server over streamable HTTP. `ask` answers a question;
`get_section` and `get_document` read further into its sources; `feedback` rates an answer."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from librarian.config import AGENT_MODEL, SERVE_HOST
from librarian.db import Session
from librarian.models import Ask, AskFeedback
from librarian.retrieve import documents
from librarian.retrieve.ask import ask
from librarian.retrieve.result import Result
from librarian.retrieve.trace import tracer
from librarian.retrieve.trace.tracer import PostgresStore
from librarian.serve.auth import Auth, guarded

# How often a running ask tells a client that asked for progress it is still going.
PROGRESS_SECONDS = 10

# The asks' own threads: a long ask never holds up the auth check of another request,
# which runs in the event loop's default pool.
ASKS = ThreadPoolExecutor(thread_name_prefix="ask")

server = MCPServer("librarian")


class Rating(StrEnum):
    good = auto()
    bad = auto()


@server.tool(name="ask")
async def ask_tool(question: str, ctx: Context[Any, Any]) -> Result:
    """Ask the library one question, in Italian. Every value and passage in the result points
    at a source: a document and its section. A source's `section_id` and `document_id` read
    further, with `get_section` and `get_document`; `section_chars` and `document_chars` are
    how long each is. `file` links to the document's file. `trace_id` names the record of the
    run."""
    # When it started, plus a random suffix: sorts by time, unique within a second.
    correlation_id = f"mcp-{datetime.now():%Y-%m-%dT%H-%M-%S}-{uuid4().hex[:6]}"
    # In a thread of its own: the event loop serves other requests while this one digs.
    loop = asyncio.get_running_loop()
    work = loop.run_in_executor(ASKS, ask, question, AGENT_MODEL, correlation_id)
    seconds = 0
    await asyncio.wait([work], timeout=PROGRESS_SECONDS)
    while not work.done():
        seconds += PROGRESS_SECONDS
        await ctx.report_progress(seconds, message=f"still digging, {seconds} s")
        await asyncio.wait([work], timeout=PROGRESS_SECONDS)
    try:
        inquiry = work.result()
    except Exception as error:
        message = f"the ask failed ({type(error).__name__}), trace_id {correlation_id}"
        raise ToolError(message) from error
    if inquiry.result is None:
        raise ToolError(f"the ask ended with no result, trace_id {correlation_id}")
    return inquiry.result


@server.tool()
def get_section(section_id: int) -> str:
    """A section's whole text, under its heading: the `section_id` of a source `ask` gave,
    `section_chars` long."""
    text = documents.section(section_id)
    if text is None:
        raise ToolError(f"no section {section_id}")
    return text


@server.tool()
def get_document(document_id: int) -> str:
    """A whole document's text, its sections in order, each under its heading: the
    `document_id` of a source `ask` gave, `document_chars` long."""
    text = documents.document(document_id)
    if text is None:
        raise ToolError(f"no document {document_id}")
    return text


@server.tool()
def feedback(trace_id: str, rating: Rating, note: str | None = None) -> str:
    """Rate an answer `ask` gave, by its `trace_id`: good or bad, with a note saying why."""
    # The rating points at the run's asks row, which only the postgres store writes.
    if not isinstance(tracer.store, PostgresStore):
        raise ToolError(
            "feedback needs LIBRARIAN_TRACE_STORE=postgres; this server traces to files"
        )
    with Session() as session:
        if session.get(Ask, trace_id) is None:
            raise ToolError(f"no ask with trace_id {trace_id}")
        row = AskFeedback(
            correlation_id=trace_id, name="rating", value=rating, comment=note, source="mcp"
        )
        session.add(row)
        session.commit()
    return f"rated {rating}"


def app() -> Auth:
    """The server as librarian-serve runs it, behind the auth."""
    return guarded(server.streamable_http_app(host=SERVE_HOST))
