from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from librarian.db import Base

DIMENSIONS = 1024


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    document_section_id: Mapped[int] = mapped_column(ForeignKey("document_sections.id"), index=True)
    text: Mapped[str]
    model: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSIONS))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
