"""A section or a whole document as text, read as `librarian_reader`: what the outside agent's
`get_section` and `get_document` return, and what a source's sizes measure. And each
document's status and file, read as the app's login.

A section's text is uncut (search trims long ones) and sits under its heading; a document is
its sections in order.
"""

from typing import Any, LiteralString

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from librarian.adapters.postgres.sql import ReaderConnections

SECTIONS_SQL = """SELECT s.id, s.heading, s.text
FROM documents d LEFT JOIN document_sections s ON s.document_id = d.id
WHERE d.id = %s ORDER BY s.position"""
SECTION_SQL = "SELECT heading, text FROM document_sections WHERE id = %s"


class PostgresDocuments:
    def __init__(self, connections: ReaderConnections, sessions: sessionmaker[Session]) -> None:
        self.connections = connections
        self.sessions = sessions

    def section(self, section_id: int) -> str | None:
        rows = self._read(SECTION_SQL, section_id)
        if not rows:
            return None
        return _under_heading(rows[0][0], rows[0][1])

    def document(self, document_id: int) -> str | None:
        texts = self.sections(document_id)
        if texts is None:
            return None
        return "\n\n".join(texts.values())

    def sections(self, document_id: int) -> dict[int, str] | None:
        rows = self._read(SECTIONS_SQL, document_id)
        if not rows:
            return None
        texts: dict[int, str] = {}
        for row in rows:
            # A document with no sections comes back as one row of nulls.
            if row[0] is not None:
                texts[row[0]] = _under_heading(row[1], row[2])
        return texts

    def statuses(self, document_ids: list[int]) -> dict[int, str]:
        statuses: dict[int, str] = {}
        if not document_ids:
            return statuses
        with self.sessions() as session:
            rows = session.execute(
                text("SELECT id, status FROM documents WHERE id = ANY(:ids)"),
                {"ids": document_ids},
            ).all()
        for row in rows:
            statuses[row[0]] = row[1]
        return statuses

    def paths(self, document_ids: list[int]) -> dict[int, str]:
        paths: dict[int, str] = {}
        if not document_ids:
            return paths
        with self.sessions() as session:
            rows = session.execute(
                text(
                    "SELECT d.id, i.destination_path FROM documents d"
                    " JOIN ingestions i ON i.id = d.ingestion_id"
                    " WHERE d.id = ANY(:ids) AND i.destination_path IS NOT NULL"
                ),
                {"ids": document_ids},
            ).all()
        for row in rows:
            paths[row[0]] = row[1]
        return paths

    def _read(self, query: LiteralString, value: int) -> list[tuple[Any, ...]]:
        connection = self.connections.get()
        with connection.transaction(force_rollback=True), connection.cursor() as cursor:
            cursor.execute(query, (value,))
            return cursor.fetchall()


def _under_heading(heading: str, body: str) -> str:
    if not heading:
        return body
    return f"## {heading}\n\n{body}"
