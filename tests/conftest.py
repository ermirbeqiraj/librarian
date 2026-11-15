"""Test setup: the adapters run against a throwaway `librarian_test` database on the compose
Postgres, migrated once per session. When Postgres is unreachable the database tests skip.
"""

import os
from collections.abc import Callable
from pathlib import Path

TEST_DATABASE_URL = os.environ.get(
    "LIBRARIAN_TEST_DATABASE_URL",
    "postgresql+psycopg://librarian:librarian@127.0.0.1:5432/librarian_test",
)
TEST_READER_URL = os.environ.get(
    "LIBRARIAN_TEST_READER_DATABASE_URL",
    "postgresql+psycopg://librarian_reader:librarian_reader@127.0.0.1:5432/librarian_test",
)
# A host built in a test points at the test database too: set before any librarian import.
os.environ["LIBRARIAN_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["LIBRARIAN_READER_DATABASE_URL"] = TEST_READER_URL

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session as DbSession

from librarian.adapters.file_trace_store import FileStore
from librarian.adapters.postgres import db as database
from librarian.adapters.postgres.models import Chunk, Document, DocumentSection, Ingestion
from librarian.adapters.postgres.models.chunk import DIMENSIONS
from librarian.adapters.postgres.sql import ReaderConnections
from librarian.adapters.postgres.trace_store import PostgresStore
from librarian.application.ingest.document import DocumentStatus, IngestionStatus
from librarian.application.retrieve.ports import Event, TraceStore
from librarian.application.retrieve.tracer import Tracer

# The reader role's statement_timeout, as infra provisions it.
STATEMENT_TIMEOUT_SECONDS = 5
SESSIONS = database.sessions(TEST_DATABASE_URL)
READER = ReaderConnections(TEST_READER_URL)


def unit_vector(index: int) -> list[float]:
    """A one-hot embedding: cosine distance to unit_vector(i) is 0, to any other unit is 1."""
    vector = [0.0] * DIMENSIONS
    vector[index] = 1.0
    return vector


@pytest.fixture(scope="session")
def test_db() -> None:
    """The compose Postgres with the schema migrated to head; skipped when unreachable."""
    name = make_url(TEST_DATABASE_URL).database or "librarian_test"
    admin_url = make_url(TEST_DATABASE_URL).set(database="postgres")
    try:
        probe = create_engine(admin_url, connect_args={"connect_timeout": 3})
        with probe.connect() as connection:
            connection.execute(text("SELECT 1"))
        probe.dispose()
    except Exception:  # noqa: BLE001
        pytest.skip("compose Postgres is not reachable, database tests skipped")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    # Extensions are the DBA's, not a migration's; here the compose superuser is the DBA.
    test_admin = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with test_admin.connect() as connection:
        connection.execute(text("CREATE EXTENSION vector"))
        connection.execute(text("CREATE EXTENSION unaccent"))
    test_admin.dispose()
    config = Config()
    config.set_main_option("script_location", str(Path(database.__file__).parent / "migrations"))
    command.upgrade(config, "head")
    _ensure_reader_role(admin, TEST_DATABASE_URL)
    yield
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def _ensure_reader_role(admin: Engine, test_database_url: str) -> None:
    """The dev cluster's bootstrap superuser creates the SQL tool's read-only role.

    No app migration creates roles or logins anymore — a managed cluster's migration
    role has no CREATEROLE — so on the homeserver the role comes from infra. In the
    throwaway test database the test setup makes it, with the same borders.
    """
    password = (make_url(TEST_READER_URL).password or "").replace("'", "''")
    with admin.connect() as connection:
        connection.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'librarian_reader') THEN
                        CREATE ROLE librarian_reader LOGIN PASSWORD '{password}';
                    ELSE
                        ALTER ROLE librarian_reader PASSWORD '{password}';
                    END IF;
                END $$;
                """
            )
        )
        connection.execute(
            text("ALTER ROLE librarian_reader SET default_transaction_read_only = on")
        )
        timeout = f"{STATEMENT_TIMEOUT_SECONDS}s"
        connection.execute(text(f"ALTER ROLE librarian_reader SET statement_timeout = '{timeout}'"))
    test_admin = create_engine(test_database_url, isolation_level="AUTOCOMMIT")
    with test_admin.connect() as connection:
        connection.execute(text("GRANT USAGE ON SCHEMA public TO librarian_reader"))
        connection.execute(text("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM librarian_reader"))
        connection.execute(text("GRANT SELECT ON documents, document_sections TO librarian_reader"))
    test_admin.dispose()


@pytest.fixture
def db(test_db: None) -> DbSession:
    """A session over the migrated test database, wiped after each test."""
    with SESSIONS() as session:
        yield session
    with SESSIONS() as session:
        for table in reversed(database.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture
def add_document(db: DbSession) -> Callable[..., Document]:
    """Insert one document with its sections and chunks.

    sections: list of (heading, text, chunks), chunks: list of (chunk text, vector), the
    vector an index into unit_vector() or a full embedding, so tests steer cosine distance.
    """

    def _add(
        *,
        kind: str = "invoice",
        validity: Range | None = None,
        fields: dict | None = None,
        status: DocumentStatus = DocumentStatus.confirmed,
        sections: list[tuple[str, str, list[tuple[str, int | list[float]]]]] = (),
    ) -> Document:
        ingestion = Ingestion(
            original_file_name="test.pdf", file_size=1, status=IngestionStatus.done
        )
        document = Document(
            kind=kind,
            validity=validity,
            fields=fields if fields is not None else {"issuer": "Test S.p.A."},
            parser="test",
            problems=[],
            status=status,
        )
        ingestion.document = document
        db.add(ingestion)
        for position, (heading, body, chunks) in enumerate(sections):
            row = DocumentSection(position=position, heading=heading, text=body)
            for chunk_text, vector in chunks:
                embedding = unit_vector(vector) if isinstance(vector, int) else vector
                row.chunks.append(Chunk(text=chunk_text, model="test", embedding=embedding))
            document.sections.append(row)
        db.commit()
        return document

    return _add


@pytest.fixture(params=["file", "postgres"])
def trace_store(request: pytest.FixtureRequest, tmp_path: Path) -> TraceStore:
    """An empty store, once per store: files under tmp_path, then the test database."""
    if request.param == "postgres":
        request.getfixturevalue("db")
        return PostgresStore(SESSIONS)
    return FileStore(tmp_path / "traces")


@pytest.fixture
def tracer(trace_store: TraceStore) -> Tracer:
    """A tracer on `trace_store`; whatever is still waiting goes to it at the end."""
    tracer = Tracer(trace_store)
    yield tracer
    tracer.flush()


class RefusingStore:
    """A store that is down for its first `times` writes, then writes to `store`."""

    def __init__(self, store: TraceStore, times: int) -> None:
        self.store = store
        self.times = times

    def write(self, correlation_id: str, events: list[Event]) -> None:
        if self.times > 0:
            self.times -= 1
            raise OSError("No space left on device")
        self.store.write(correlation_id, events)

    def read(self, correlation_id: str) -> list[Event]:
        return self.store.read(correlation_id)
