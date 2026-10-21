from sqlalchemy import select
from sqlalchemy.orm import Session

from librarian.models import Ingestion, IngestionStatus


def find_done_by_hash(session: Session, content_hash: str) -> Ingestion | None:
    return session.scalars(
        select(Ingestion)
        .where(Ingestion.content_hash == content_hash, Ingestion.status == IngestionStatus.done)
        .limit(1)
    ).first()


def add(session: Session, ingestion: Ingestion) -> None:
    session.add(ingestion)
