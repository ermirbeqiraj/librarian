from datetime import datetime
from enum import StrEnum, auto

from sqlalchemy import DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column

from librarian.adapters.postgres.db import Base


class AskStatus(StrEnum):
    # The result's statuses, plus a run that raised.
    found = auto()
    partial = auto()
    not_found = auto()
    error = auto()


class Ask(Base):
    """One run of `ask`: written by its `started` event, completed by `finished` or `failed`."""

    __tablename__ = "asks"

    correlation_id: Mapped[str] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Null while it runs, and after a hard kill.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    question: Mapped[str]
    agent_model: Mapped[str]
    refine_model: Mapped[str]
    reasoning: Mapped[str]
    prompt: Mapped[str]
    # Null when git can't answer, as in the image.
    git_sha: Mapped[str | None]
    # Null until it ends, and when it ends without a submit.
    status: Mapped[AskStatus | None] = mapped_column(
        Enum(AskStatus, name="status", native_enum=False, create_constraint=True)
    )
    error: Mapped[str | None]
    tokens_in: Mapped[int | None]
    tokens_out: Mapped[int | None]
    rounds: Mapped[int | None]
    calls: Mapped[int | None]
    ms: Mapped[int | None]
