"""Every ask's trace in Postgres: its `asks` row and its `ask_events`."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from librarian.adapters.postgres.models import Ask, AskEvent, AskStatus
from librarian.application.retrieve.ports import Event
from librarian.application.retrieve.tracer import ENDS


class PostgresStore:
    """The run's `asks` row, created by `started` and completed by `finished` or `failed`,
    and its events in `ask_events`, in one transaction: an event never exists without its run."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def write(self, correlation_id: str, events: list[Event]) -> None:
        with self.sessions() as session:
            run = session.get(Ask, correlation_id)
            for event in events:
                data = event.model_dump(mode="json")["data"]
                if event.step == "started":
                    run = Ask(
                        correlation_id=correlation_id,
                        started_at=event.at,
                        question=data["question"],
                        agent_model=data["agent_model"],
                        refine_model=data["refine_model"],
                        reasoning=data["reasoning"],
                        prompt=data["prompt"],
                        git_sha=data["git_sha"],
                    )
                    session.add(run)
                elif event.step in ENDS:
                    if run is None:
                        raise RuntimeError(f"no asks row for {correlation_id}")
                    run.finished_at = event.at
                    if event.step == "failed":
                        run.status = AskStatus.error
                        run.error = data["error"]
                    elif data["status"] is not None:
                        run.status = AskStatus(data["status"])
                    run.tokens_in = data["input_tokens"]
                    run.tokens_out = data["output_tokens"]
                    run.rounds = data["rounds"]
                    run.calls = data["calls"]
                    run.ms = event.ms
                session.add(
                    AskEvent(
                        correlation_id=correlation_id,
                        seq=event.seq,
                        at=event.at,
                        step=event.step,
                        round=event.round,
                        kind=event.kind,
                        ms=event.ms,
                        data=data,
                    )
                )
            session.commit()

    def read(self, correlation_id: str) -> list[Event]:
        query = (
            select(AskEvent).where(AskEvent.correlation_id == correlation_id).order_by(AskEvent.seq)
        )
        events: list[Event] = []
        with self.sessions() as session:
            for row in session.scalars(query):
                events.append(
                    Event(
                        seq=row.seq,
                        at=row.at,
                        step=row.step,
                        round=row.round,
                        kind=row.kind,
                        ms=row.ms,
                        data=row.data,
                    )
                )
        return events
