from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from librarian.db import Base
from librarian.models.chunk import Chunk


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    position: Mapped[int]
    heading: Mapped[str]
    text: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chunks: Mapped[list[Chunk]] = relationship()
