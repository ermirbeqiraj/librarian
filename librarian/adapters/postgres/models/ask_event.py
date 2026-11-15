from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from librarian.adapters.postgres.db import Base


class AskEvent(Base):
    """One event of a run's trace, the .jsonl line for line."""

    __tablename__ = "ask_events"

    correlation_id: Mapped[str] = mapped_column(
        ForeignKey("asks.correlation_id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    step: Mapped[str]
    # Round events only.
    round: Mapped[int | None]
    kind: Mapped[str]
    # On the events that end a step.
    ms: Mapped[int | None]
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
