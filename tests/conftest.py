"""Test setup: the app runs against a throwaway `librarian_test` database on the compose
Postgres, migrated once per session. When Postgres is unreachable the database tests skip.
"""

import os
from collections.abc import Callable
from pathlib import Path

TEST_DATABASE_URL = os.environ.get(
    "LIBRARIAN_TEST_DATABASE_URL",
    "postgresql+psycopg://librarian:librarian@127.0.0.1:5432/librarian_test",
)
# Point the app at the test database before any librarian module is imported.
os.environ["LIBRARIAN_DATABASE_URL"] = TEST_DATABASE_URL

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session as DbSession

import librarian.db
from librarian.models import (
    Chunk,
    Document,
    DocumentSection,
    DocumentStatus,
    Ingestion,
    IngestionStatus,
)
from librarian.models.chunk import DIMENSIONS

Base = librarian.db.Base

librarian.db.engine.echo = False


def unit_vector(index: int) -> list[float]:
    """A one-hot embedding: cosine distance to unit_vector(i) is 0, to any other unit is 1."""
    vector = [0.0] * DIMENSIONS
    vector[index] = 1.0
    return vector


@pytest.fixture(scope="session")
def test_db() -> None:
    """The compose Postgres with the schema migrated to head; skipped when unreachable."""
    name = make_url(TEST_DATABASE_URL).database or "librarian_test"
    admin_url = str(make_url(TEST_DATABASE_URL).set(database="postgres"))
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
    config = Config()
    config.set_main_option(
        "script_location", str(Path(librarian.db.__file__).parent / "migrations")
    )
    command.upgrade(config, "head")
    yield
    librarian.db.engine.dispose()
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def db(test_db: None) -> DbSession:
    """A session over the migrated test database, wiped after each test."""
    with librarian.db.Session() as session:
        yield session
    with librarian.db.Session() as session:
        for table in reversed(Base.metadata.sorted_tables):
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
