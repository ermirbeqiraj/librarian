from typing import Protocol

from librarian.retrieve.result import Result


class Retriever(Protocol):
    def ask(self, question: str) -> Result: ...


class Blank:
    """Answers nothing, so the eval runs before there is anything to measure."""

    def ask(self, question: str) -> Result:
        return Result(status=None, values=[], passages=[], sources=[], trace_id=None)
