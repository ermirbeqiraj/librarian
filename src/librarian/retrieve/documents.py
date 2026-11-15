"""A section or a whole document as text, read as `librarian_reader`: what the outside agent's
`get_section` and `get_document` return, and what a source's sizes measure.

A section's text is uncut (search trims long ones) and sits under its heading; a document is
its sections in order.
"""

from typing import Any, LiteralString

from librarian.retrieve.sql import reader_connection

SECTIONS_SQL = """SELECT s.id, s.heading, s.text
FROM documents d LEFT JOIN document_sections s ON s.document_id = d.id
WHERE d.id = %s ORDER BY s.position"""
SECTION_SQL = "SELECT heading, text FROM document_sections WHERE id = %s"


def section(section_id: int) -> str | None:
    """None when there is no such section."""
    rows = _read(SECTION_SQL, section_id)
    if not rows:
        return None
    return _under_heading(rows[0][0], rows[0][1])


def document(document_id: int) -> str | None:
    """None when there is no such document."""
    texts = sections(document_id)
    if texts is None:
        return None
    return joined(texts)


def sections(document_id: int) -> dict[int, str] | None:
    """The document's sections in order, by id, as `section` gives each; None when there is
    no such document."""
    rows = _read(SECTIONS_SQL, document_id)
    if not rows:
        return None
    texts: dict[int, str] = {}
    for row in rows:
        # A document with no sections comes back as one row of nulls.
        if row[0] is not None:
            texts[row[0]] = _under_heading(row[1], row[2])
    return texts


def joined(texts: dict[int, str]) -> str:
    """The whole document, from its `sections`."""
    return "\n\n".join(texts.values())


def _under_heading(heading: str, text: str) -> str:
    if not heading:
        return text
    return f"## {heading}\n\n{text}"


def _read(query: LiteralString, value: int) -> list[tuple[Any, ...]]:
    connection = reader_connection()
    with connection.transaction(force_rollback=True), connection.cursor() as cursor:
        cursor.execute(query, (value,))
        return cursor.fetchall()
