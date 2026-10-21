from datetime import datetime
from enum import StrEnum, auto

from sqlalchemy import BigInteger, DateTime, Enum, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from librarian.db import Base
from librarian.models.document import Document


class IngestionStatus(StrEnum):
    received = auto()
    done = auto()
    duplicate = auto()
    failed = auto()


class Ingestion(Base):
    __tablename__ = "ingestions"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    original_file_name: Mapped[str]
    destination_path: Mapped[str | None]
    file_size: Mapped[int] = mapped_column(BigInteger)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="status", native_enum=False, create_constraint=True)
    )
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    document: Mapped[Document | None] = relationship()
