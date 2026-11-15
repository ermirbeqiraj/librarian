"""Every file's `ingestions` row, and the document read from it: the plain values of ingest
mapped to the rows."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session, sessionmaker

from librarian.adapters.postgres import models
from librarian.application.ingest import document
from librarian.application.ingest.document import IngestionStatus


class PostgresIngestions:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def start(self, ingestion: document.Ingestion) -> int:
        row = models.Ingestion(
            original_file_name=ingestion.original_file_name,
            file_size=ingestion.file_size,
            status=ingestion.status,
        )
        with self.sessions() as session:
            session.add(row)
            session.commit()
            return row.id

    def is_duplicate(self, content_hash: str) -> bool:
        query = (
            select(models.Ingestion.id)
            .where(
                models.Ingestion.content_hash == content_hash,
                models.Ingestion.status == IngestionStatus.done,
            )
            .limit(1)
        )
        with self.sessions() as session:
            return session.scalars(query).first() is not None

    def finish(self, ingestion: document.Ingestion) -> None:
        with self.sessions() as session:
            row = session.get_one(models.Ingestion, ingestion.id)
            row.status = ingestion.status
            row.content_hash = ingestion.content_hash
            row.error = ingestion.error
            row.destination_path = ingestion.destination_path
            if ingestion.document is not None:
                row.document = _document(ingestion.document)
            session.commit()


def _document(read: document.Document) -> models.Document:
    validity = None
    if read.validity is not None:
        validity = Range(read.validity.start, read.validity.end, bounds="[]")
    row = models.Document(
        kind=read.kind,
        validity=validity,
        fields=read.fields,
        parser=read.parser,
        description=read.description,
        problems=read.problems,
        status=read.status,
    )
    for position, section in enumerate(read.sections):
        section_row = models.DocumentSection(
            position=position, heading=section.heading, text=section.text
        )
        for piece in section.chunks:
            section_row.chunks.append(
                models.Chunk(text=piece.text, model=piece.model, embedding=piece.embedding)
            )
        row.sections.append(section_row)
    return row
