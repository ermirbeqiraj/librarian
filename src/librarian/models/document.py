from datetime import date, datetime
from enum import StrEnum, auto
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Identity, Index, func
from sqlalchemy.dialects.postgresql import DATERANGE, JSONB, Range
from sqlalchemy.orm import Mapped, mapped_column, relationship

from librarian.db import Base
from librarian.models.document_section import DocumentSection


class DocumentStatus(StrEnum):
    draft = auto()
    confirmed = auto()


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_validity", "validity", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    ingestion_id: Mapped[int] = mapped_column(ForeignKey("ingestions.id"))
    kind: Mapped[str]
    validity: Mapped[Range[date] | None] = mapped_column(DATERANGE)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB)
    description: Mapped[str | None]
    problems: Mapped[list[dict[str, str]]] = mapped_column(JSONB)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="status", native_enum=False, create_constraint=True)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sections: Mapped[list[DocumentSection]] = relationship()
