from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from librarian.adapters.postgres.db import Base


class AskFeedback(Base):
    """A score on a run, shaped like Langfuse's: several per run, `name` says which kind."""

    __tablename__ = "ask_feedback"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    correlation_id: Mapped[str] = mapped_column(
        ForeignKey("asks.correlation_id", ondelete="CASCADE")
    )
    # rating for now; other kinds later without a migration.
    name: Mapped[str]
    # good or bad, for a rating.
    value: Mapped[str]
    comment: Mapped[str | None]
    # Who rated: the outside agent, or the user by hand.
    source: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
