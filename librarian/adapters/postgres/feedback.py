"""Ratings of runs, in `ask_feedback`: shaped like Langfuse's scores."""

from sqlalchemy.orm import Session, sessionmaker

from librarian.adapters.postgres.models import Ask, AskFeedback


class PostgresFeedback:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def rate(self, trace_id: str, rating: str, note: str | None, source: str) -> bool:
        with self.sessions() as session:
            if session.get(Ask, trace_id) is None:
                return False
            row = AskFeedback(
                correlation_id=trace_id, name="rating", value=rating, comment=note, source=source
            )
            session.add(row)
            session.commit()
        return True
