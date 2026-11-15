"""Builds the adapters from the config and hands them to the application. Nothing connects
until it is first used."""

from librarian.adapters.docling import Docling
from librarian.adapters.embedder import TeiEmbedder
from librarian.adapters.file_trace_store import FileStore
from librarian.adapters.inbox import FolderInbox
from librarian.adapters.mistral import Mistral
from librarian.adapters.ocr import MistralOcr
from librarian.adapters.postgres import db
from librarian.adapters.postgres.documents import PostgresDocuments
from librarian.adapters.postgres.feedback import PostgresFeedback
from librarian.adapters.postgres.ingestions import PostgresIngestions
from librarian.adapters.postgres.search import PostgresSearch
from librarian.adapters.postgres.sql import PostgresSql, ReaderConnections
from librarian.adapters.postgres.trace_store import PostgresStore
from librarian.application.ingest.drafter import drafter
from librarian.application.ingest.pipeline import Pipeline
from librarian.application.retrieve import refine
from librarian.application.retrieve.ask import Asker
from librarian.application.retrieve.ports import Feedback, TraceStore
from librarian.application.retrieve.tracer import Tracer
from librarian.hosts import config
from librarian.hosts.git import git_sha

SESSIONS = db.sessions(config.DATABASE_URL)
READER = ReaderConnections(config.READER_DATABASE_URL)


def pipeline() -> Pipeline:
    embedder = TeiEmbedder(config.EMBEDDER_URL)
    return Pipeline(
        reader=Docling(config.DOCLING_URL),
        ocr=MistralOcr(),
        llm=Mistral(drafter.MODEL),
        embedder=embedder,
        ingestions=PostgresIngestions(SESSIONS),
        inbox=FolderInbox(config.ROOT),
    )


def trace_store() -> TraceStore:
    """Where every ask's trace goes: files under ROOT/traces, or Postgres."""
    if config.TRACE_STORE == "file":
        return FileStore(config.ROOT / "traces")
    if config.TRACE_STORE == "postgres":
        return PostgresStore(SESSIONS)
    raise ValueError(f"LIBRARIAN_TRACE_STORE is {config.TRACE_STORE!r}, not file or postgres")


def asker(model: str) -> Asker:
    """An ask with `model` as the agent's model."""
    return Asker(
        agent_chat=Mistral(model),
        refine_chat=Mistral(refine.MODEL),
        search=search(),
        sql=PostgresSql(READER),
        documents=documents(),
        tracer=Tracer(trace_store()),
        context=context,
        file_url=config.FILE_URL,
        git_sha=git_sha(),
    )


def search() -> PostgresSearch:
    return PostgresSearch(SESSIONS, TeiEmbedder(config.EMBEDDER_URL))


def documents() -> PostgresDocuments:
    return PostgresDocuments(READER, SESSIONS)


def feedback() -> Feedback | None:
    """A rating points at its run's asks row, which only the postgres store writes."""
    if config.TRACE_STORE != "postgres":
        return None
    return PostgresFeedback(SESSIONS)


def context() -> str:
    """ROOT/context.md, written by hand; empty without one."""
    path = config.ROOT / "context.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
