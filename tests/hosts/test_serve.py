import re
import socket
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import httpx
import httpx2
import jwt
import pytest
import uvicorn
from conftest import READER, SESSIONS
from cryptography.hazmat.primitives.asymmetric import rsa
from fakes import Recorder
from jwt import PyJWKClient
from jwt.algorithms import RSAAlgorithm
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent
from sqlalchemy import select

from librarian.adapters.postgres.documents import PostgresDocuments
from librarian.adapters.postgres.feedback import PostgresFeedback
from librarian.adapters.postgres.models import Ask, AskFeedback, Ingestion
from librarian.application.retrieve.ask import Asker
from librarian.application.retrieve.result import Inquiry, LinkedSource, Result, Status, Value
from librarian.hosts.mcp import auth, server

TOKEN = "a-token-the-test-made-32-characters-long"
BEARER = {"Authorization": f"Bearer {TOKEN}"}
QUESTION = {"question": "quanto ho pagato"}
TEAM = "test-team"
ISSUER = f"https://{TEAM}.cloudflareaccess.com"
AUD = "test-aud-tag"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Answers:
    """An asker whose every ask is `answer(question, correlation_id)`."""

    def __init__(self, answer: Callable[[str, str], Inquiry]) -> None:
        self.answer = answer

    def ask(self, question: str, correlation_id: str) -> Inquiry:
        return self.answer(question, correlation_id)


def built(answer: Callable[[str, str], Inquiry] | None = None, feedback: Any = None) -> Any:
    """The server's tools on the test database; `ask` answers with `answer`."""
    documents = PostgresDocuments(READER, SESSIONS)
    return server.build(Answers(answer or fake_ask), documents, feedback)


@pytest.fixture
def serve() -> Any:
    """Starts the server as librarian-serve runs it, on a free port, and returns its URL.
    Set the auth before calling it: the server reads it when it starts."""
    servers: list[uvicorn.Server] = []
    threads: list[threading.Thread] = []

    def start(answer: Callable[[str, str], Inquiry] | None = None, feedback: Any = None) -> str:
        listening = socket.socket()
        listening.bind(("127.0.0.1", 0))
        port = listening.getsockname()[1]
        app = server.app(built(answer, feedback))
        each = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        thread = threading.Thread(target=each.run, kwargs={"sockets": [listening]})
        thread.start()
        servers.append(each)
        threads.append(thread)
        deadline = time.monotonic() + 10
        while not each.started:
            assert thread.is_alive() and time.monotonic() < deadline, "the server didn't start"
            time.sleep(0.01)
        return f"http://127.0.0.1:{port}/mcp"

    yield start
    for each in servers:
        each.should_exit = True
    for thread in threads:
        thread.join()


@pytest.fixture
def bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "AUTH", "bearer")
    monkeypatch.setattr(auth, "BEARER_TOKEN", TOKEN)


class AccessKeys(PyJWKClient):
    """The Access certs endpoint, answered with the test's own public key."""

    def fetch_data(self) -> Any:
        assert self.uri == f"{ISSUER}/cdn-cgi/access/certs"
        public = RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
        public["kid"] = "test-kid"
        return {"keys": [public]}


@pytest.fixture
def access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "AUTH", "access")
    monkeypatch.setattr(auth, "ACCESS_TEAM", TEAM)
    monkeypatch.setattr(auth, "ACCESS_AUD", AUD)
    monkeypatch.setattr(auth, "PyJWKClient", AccessKeys)


def access_jwt(**changes: Any) -> str:
    """A JWT as Access signs it; `changes` overrides its claims, `key` the signing key and
    `minutes` how long it has left."""
    key = changes.pop("key", KEY)
    minutes = changes.pop("minutes", 5)
    claims = {
        "iss": ISSUER,
        "aud": [AUD],
        "email": "someone@example.com",
        "exp": datetime.now(UTC) + timedelta(minutes=minutes),
    }
    claims.update(changes)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-kid"})


def fake_ask(question: str, correlation_id: str) -> Inquiry:
    result = Result(
        status=Status.found,
        values=[Value(name="total", value="84.20", unit="EUR", source=1)],
        passages=[],
        sources=[LinkedSource(id=1, document_id=7, kind="invoice", section="Totale", section_id=3)],
        trace_id=correlation_id,
    )
    return Inquiry(correlation_id=correlation_id, question=question, result=result)


def call(
    url: str,
    headers: dict[str, str],
    tool: str,
    arguments: dict[str, Any],
    progress: Callable[..., Any] | None = None,
) -> CallToolResult:
    """One tool call through the SDK's client, over HTTP."""

    async def calling() -> CallToolResult:
        http = httpx2.AsyncClient(headers=headers)
        async with http, Client(streamable_http_client(url, http_client=http)) as client:
            return await client.call_tool(tool, arguments, progress_callback=progress)

    return anyio.run(calling)


def text(result: CallToolResult) -> str:
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


def test_ask_over_the_server_returns_the_result_with_its_trace_id(serve: Any, bearer: None) -> None:
    result = call(serve(), BEARER, "ask", QUESTION)
    assert not result.is_error
    returned = result.structured_content
    assert returned is not None
    assert re.fullmatch(r"mcp-\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d-[0-9a-f]{6}", returned["trace_id"])
    assert returned["status"] == "found"
    assert returned["values"][0]["value"] == "84.20"
    assert returned["sources"][0]["section"] == "Totale"


def failing_ask(question: str, correlation_id: str) -> Inquiry:
    raise RuntimeError("429 Too Many Requests")


def never_submits(question: str, correlation_id: str) -> Inquiry:
    return Inquiry(correlation_id=correlation_id, question=question)


@pytest.mark.parametrize("fake", [failing_ask, never_submits])
def test_an_ask_with_no_result_is_a_tool_error_naming_its_trace(
    serve: Any, bearer: None, fake: Any
) -> None:
    result = call(serve(fake), BEARER, "ask", QUESTION)
    assert result.is_error
    assert re.search(r"trace_id mcp-\S+-[0-9a-f]{6}$", text(result))


def test_two_slow_asks_run_at_once_and_report_progress(
    serve: Any, bearer: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each ask waits for the other: on the event loop, the first would block the second.
    both = threading.Barrier(2, timeout=5)

    def slow_ask(question: str, correlation_id: str) -> Inquiry:
        both.wait()
        time.sleep(0.3)
        return fake_ask(question, correlation_id)

    monkeypatch.setattr(server, "PROGRESS_SECONDS", 0.1)
    url = serve(slow_ask)
    progress: list[float] = []
    results: list[CallToolResult] = []

    async def on_progress(done: float, total: float | None, message: str | None) -> None:
        progress.append(done)

    def asking() -> None:
        results.append(call(url, BEARER, "ask", QUESTION, on_progress))

    threads = [threading.Thread(target=asking), threading.Thread(target=asking)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 2
    for result in results:
        assert not result.is_error
    assert progress


@pytest.mark.parametrize("header", [None, "Bearer wrong-token", TOKEN, f"Basic {TOKEN}"])
def test_bearer_refuses_a_wrong_or_missing_token(
    serve: Any, bearer: None, header: str | None
) -> None:
    headers: dict[str, str] = {}
    if header is not None:
        headers["Authorization"] = header
    response = httpx.post(serve(), headers=headers, json={})
    assert response.status_code == 401


def test_access_lets_a_valid_jwt_through(serve: Any, access: None) -> None:
    result = call(serve(), {"Cf-Access-Jwt-Assertion": access_jwt()}, "ask", QUESTION)
    assert not result.is_error


@pytest.mark.parametrize(
    "changes",
    [
        None,
        {"key": OTHER_KEY},
        {"aud": ["another-app"]},
        {"iss": "https://another-team.cloudflareaccess.com"},
        {"minutes": -1},
        "not-a-jwt",
    ],
    ids=["missing", "wrong signature", "wrong aud", "wrong iss", "expired", "garbage"],
)
def test_access_refuses_a_bad_or_missing_jwt(
    serve: Any,
    access: None,
    changes: dict[str, Any] | str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if isinstance(changes, str):
        headers["Cf-Access-Jwt-Assertion"] = changes
    elif changes is not None:
        headers["Cf-Access-Jwt-Assertion"] = access_jwt(**changes)
    response = httpx.post(serve(), headers=headers, json={})
    assert response.status_code == 403
    assert "www-authenticate" not in response.headers
    err = capsys.readouterr().err
    assert "auth refused: " in err
    assert TOKEN not in err


@pytest.mark.parametrize(
    "mode, token, team",
    [
        (None, None, None),
        ("open", TOKEN, TEAM),
        ("bearer", "", None),
        ("bearer", "x" * 31, None),
        ("access", None, None),
    ],
    ids=["unset", "unknown", "bearer without token", "bearer short token", "access without team"],
)
def test_the_server_refuses_to_start_without_complete_auth(
    monkeypatch: pytest.MonkeyPatch, mode: str | None, token: str | None, team: str | None
) -> None:
    monkeypatch.setattr(auth, "AUTH", mode)
    monkeypatch.setattr(auth, "BEARER_TOKEN", token)
    monkeypatch.setattr(auth, "ACCESS_TEAM", team)
    monkeypatch.setattr(auth, "ACCESS_AUD", AUD)
    with pytest.raises(SystemExit):
        server.app(built())


@pytest.mark.parametrize(
    "template, file",
    [
        (None, None),
        ("https://files.example/home/{path}", "https://files.example/home/processed/b%20c/1.pdf"),
    ],
)
def test_a_source_gives_the_sizes_of_what_the_tools_return(
    serve: Any,
    bearer: None,
    add_document: Any,
    db: Any,
    monkeypatch: pytest.MonkeyPatch,
    template: str | None,
    file: str | None,
) -> None:
    document = add_document(
        sections=[
            ("Totale", "Totale da pagare 41,27 €", []),
            ("", "Un testo senza titolo.", []),
            ("Dettaglio", "una riga lunga " * 40, []),
        ]
    )
    other = add_document(sections=[("Altro", "Un altro documento.", [])])
    db.get(Ingestion, document.ingestion_id).destination_path = "processed/b c/1.pdf"
    db.commit()
    first = document.sections[0].id
    sources = [
        LinkedSource(id=1, document_id=document.id, kind="invoice", section="T", section_id=first),
        # The agent named a section of another document.
        LinkedSource(
            id=2,
            document_id=document.id,
            kind="invoice",
            section="Altro",
            section_id=other.sections[0].id,
        ),
        LinkedSource(id=3, document_id=document.id, kind="invoice", section=None, section_id=None),
    ]
    result = Result(status=Status.found, values=[], passages=[], sources=sources, trace_id="x")
    inquiry = Inquiry(correlation_id="x", question="q", result=result)
    linking = Asker(
        agent_chat=None,
        refine_chat=None,
        search=None,
        sql=None,
        documents=PostgresDocuments(READER, SESSIONS),
        tracer=Recorder(),
        context=lambda: "",
        file_url=template,
        git_sha=None,
    )
    linking._link(inquiry)
    url = serve()
    section = text(call(url, BEARER, "get_section", {"section_id": first}))
    whole = text(call(url, BEARER, "get_document", {"document_id": document.id}))
    assert section == "## Totale\n\nTotale da pagare 41,27 €"
    assert whole.startswith(section + "\n\nUn testo senza titolo.\n\n## Dettaglio\n\n")
    assert (sources[0].section_id, sources[0].section_chars) == (first, len(section))
    assert (sources[1].section_id, sources[1].section_chars) == (None, None)
    assert (sources[2].section_id, sources[2].section_chars) == (None, None)
    for source in sources:
        assert source.document_chars == len(whole)
        assert source.file == file


@pytest.mark.parametrize("tool", ["get_section", "get_document"])
def test_the_document_tools_error_on_an_unknown_id(
    serve: Any, bearer: None, db: Any, tool: str
) -> None:
    argument = tool.removeprefix("get_") + "_id"
    result = call(serve(), BEARER, tool, {argument: 999999})
    assert result.is_error
    assert "999999" in text(result)


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("get_section", {"section_id": 1}),
        ("get_document", {"document_id": 1}),
        ("feedback", {"trace_id": "mcp-x", "rating": "bad"}),
    ],
)
def test_the_other_tools_refuse_without_auth(
    serve: Any, bearer: None, tool: str, arguments: dict[str, Any]
) -> None:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    response = httpx.post(serve(), json=request)
    assert response.status_code == 401


@pytest.fixture
def an_ask(db: Any) -> str:
    """A made-up asks row; returns its trace_id."""
    run = Ask(
        correlation_id="mcp-test-rated",
        started_at=datetime.now(UTC),
        question="quanto ho pagato",
        agent_model="fake",
        refine_model="fake",
        reasoning="high",
        prompt="dig.md",
    )
    db.add(run)
    db.commit()
    return run.correlation_id


def test_feedback_stores_a_rating(serve: Any, bearer: None, db: Any, an_ask: str) -> None:
    arguments = {"trace_id": an_ask, "rating": "bad", "note": "il totale è di un'altra bolletta"}
    result = call(serve(feedback=PostgresFeedback(SESSIONS)), BEARER, "feedback", arguments)
    assert not result.is_error
    rows = db.scalars(select(AskFeedback)).all()
    assert len(rows) == 1
    row = rows[0]
    stored = (row.correlation_id, row.name, row.value, row.comment, row.source)
    assert stored == (an_ask, "rating", "bad", "il totale è di un'altra bolletta", "mcp")


def test_feedback_on_an_unknown_trace_is_a_tool_error(
    serve: Any, bearer: None, db: Any, an_ask: str
) -> None:
    url = serve(feedback=PostgresFeedback(SESSIONS))
    result = call(url, BEARER, "feedback", {"trace_id": "mcp-nope", "rating": "good"})
    assert result.is_error
    assert "mcp-nope" in text(result)
    assert db.scalars(select(AskFeedback)).all() == []


def test_feedback_with_the_file_store_is_a_tool_error(serve: Any, bearer: None) -> None:
    result = call(serve(), BEARER, "feedback", {"trace_id": "mcp-x", "rating": "good"})
    assert result.is_error
    assert "LIBRARIAN_TRACE_STORE=postgres" in text(result)


def test_every_tool_reads_its_instructions_file_and_every_file_has_its_tool() -> None:
    names = {"server"}
    tools = built()
    for tool in anyio.run(tools.list_tools):
        names.add(tool.name)
        assert tool.description == (server.INSTRUCTIONS / f"{tool.name}.md").read_text().strip()
    files = set()
    for path in server.INSTRUCTIONS.glob("*.md"):
        files.add(path.stem)
    assert files == names
    assert tools.instructions == (server.INSTRUCTIONS / "server.md").read_text().strip()
