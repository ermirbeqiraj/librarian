"""The outside agent's way in: an MCP server over streamable HTTP. `ask` answers a question;
`get_section` and `get_document` read further into its sources; `feedback` rates an answer."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import Any
from uuid import uuid4

import uvicorn
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from librarian.application.retrieve.ask import Asker
from librarian.application.retrieve.ports import Documents, Feedback
from librarian.application.retrieve.result import Result
from librarian.hosts import wiring
from librarian.hosts.config import AGENT_MODEL, SERVE_HOST, SERVE_PORT
from librarian.hosts.mcp.auth import Auth, guarded

# How often a running ask tells a client that asked for progress it is still going.
PROGRESS_SECONDS = 10

# The asks' own threads: a long ask never holds up the auth check of another request,
# which runs in the event loop's default pool.
ASKS = ThreadPoolExecutor(thread_name_prefix="ask")

# What the outside agent reads: the server's instructions and each tool's description.
INSTRUCTIONS = Path(__file__).parent / "instructions"


def _instructions(name: str) -> str:
    return (INSTRUCTIONS / f"{name}.md").read_text(encoding="utf-8").strip()


class Rating(StrEnum):
    good = auto()
    bad = auto()


def build(asker: Asker, documents: Documents, feedback: Feedback | None) -> MCPServer:
    """The server and its tools; `feedback` is None when traces go to files."""
    server = MCPServer("librarian", instructions=_instructions("server"))

    @server.tool(name="ask", description=_instructions("ask"))
    async def ask_tool(question: str, ctx: Context[Any, Any]) -> Result:
        # When it started, plus a random suffix: sorts by time, unique within a second.
        correlation_id = f"mcp-{datetime.now():%Y-%m-%dT%H-%M-%S}-{uuid4().hex[:6]}"
        # In a thread of its own: the event loop serves other requests while this one digs.
        loop = asyncio.get_running_loop()
        work = loop.run_in_executor(ASKS, asker.ask, question, correlation_id)
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

    @server.tool(description=_instructions("get_section"))
    def get_section(section_id: int) -> str:
        text = documents.section(section_id)
        if text is None:
            raise ToolError(f"no section {section_id}")
        return text

    @server.tool(description=_instructions("get_document"))
    def get_document(document_id: int) -> str:
        text = documents.document(document_id)
        if text is None:
            raise ToolError(f"no document {document_id}")
        return text

    @server.tool(name="feedback", description=_instructions("feedback"))
    def feedback_tool(trace_id: str, rating: Rating, note: str | None = None) -> str:
        if feedback is None:
            raise ToolError(
                "feedback needs LIBRARIAN_TRACE_STORE=postgres; this server traces to files"
            )
        if not feedback.rate(trace_id, rating, note, "mcp"):
            raise ToolError(f"no ask with trace_id {trace_id}")
        return f"rated {rating}"

    return server


def app(server: MCPServer) -> Auth:
    """The server as librarian-serve runs it, behind the auth."""
    return guarded(server.streamable_http_app(host=SERVE_HOST))


def main() -> None:
    server = build(wiring.asker(AGENT_MODEL), wiring.documents(), wiring.feedback())
    uvicorn.run(app(server), host=SERVE_HOST, port=SERVE_PORT)


if __name__ == "__main__":
    main()
