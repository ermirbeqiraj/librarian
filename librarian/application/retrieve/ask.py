"""One question in, one result out: refine, then the agent digs with the tools until it
submits, then code marks which values come from documents a parser read.

`ask` runs the steps in order. Each step fills its own part of the `Inquiry` and traces
what it did under the run's correlation id: the trace, not the `Inquiry`, is the record.
"""

import json
import time
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.parse import quote

from librarian.application.ingest.document import DocumentStatus
from librarian.application.retrieve import agent
from librarian.application.retrieve.ports import Chat, Documents, Event, Search, Sql, Usage
from librarian.application.retrieve.refine import INSTRUCTIONS as REFINE_INSTRUCTIONS
from librarian.application.retrieve.refine import Refined, refine
from librarian.application.retrieve.result import Inquiry
from librarian.application.retrieve.tracer import Tracer


class Asker:
    def __init__(
        self,
        agent_chat: Chat,
        refine_chat: Chat,
        search: Search,
        sql: Sql,
        documents: Documents,
        tracer: Tracer,
        context: Callable[[], str],
        file_url: str | None,
        git_sha: str | None,
    ) -> None:
        """`context` gives who the people, homes and things in the documents are, at each ask.
        `file_url` links a source to its file, with `{path}` in it."""
        self.agent_chat = agent_chat
        self.refine_chat = refine_chat
        self.search = search
        self.sql = sql
        self.documents = documents
        self.tracer = tracer
        self.context = context
        self.file_url = file_url
        self.git_sha = git_sha

    def ask(self, question: str, correlation_id: str) -> Inquiry:
        """The caller owns the correlation id: it names the trace and is the result's
        trace_id."""
        started = time.monotonic()
        today = date.today()
        self.tracer.trace(
            correlation_id,
            Event(
                step="started",
                kind="started",
                data={
                    "question": question,
                    "today": today.isoformat(),
                    "git_sha": self.git_sha,
                    "agent_model": self.agent_chat.model,
                    "reasoning": agent.REASONING_EFFORT,
                    "refine_model": self.refine_chat.model,
                    "prompt": agent.INSTRUCTIONS.name,
                    "refine_prompt": REFINE_INSTRUCTIONS.name,
                    "round_cap": agent.ROUNDS,
                },
            ),
        )
        inquiry = Inquiry(correlation_id=correlation_id, question=question)
        step = "refine"
        try:
            inquiry.refined = self._refine(inquiry, today)
            step = "system"
            system = self._instructions(correlation_id)
            step = "round"
            agent.dig(inquiry, self.agent_chat, self.search, self.sql, self.tracer, system)
            step = "verified"
            self._verify(inquiry)
            step = "linked"
            self._link(inquiry)
        except Exception as error:
            inquiry.ms = agent.ms(started)
            failed = _totals(inquiry)
            failed["error"] = f"{type(error).__name__}: {error}"
            failed["step"] = step
            if step == "round":
                failed["round"] = inquiry.rounds
            event = Event(step="failed", kind="failed", ms=inquiry.ms, data=failed)
            self.tracer.trace(correlation_id, event)
            raise
        inquiry.ms = agent.ms(started)
        finished = _totals(inquiry)
        finished["status"] = None
        if inquiry.result is not None:
            finished["status"] = inquiry.result.status
        event = Event(step="finished", kind="finished", ms=inquiry.ms, data=finished)
        self.tracer.trace(correlation_id, event)
        return inquiry

    def _refine(self, inquiry: Inquiry, today: date) -> Refined:
        """`refine` on the question, its model's tokens counted for the trace."""
        usage = Usage()
        started = time.monotonic()
        refined = refine(inquiry.question, today, self.refine_chat, usage)
        data: dict[str, Any] = {
            "model": self.refine_chat.model,
            "input": inquiry.question,
            "output": refined.model_dump(mode="json", by_alias=True)["queries"],
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        }
        event = Event(step="refine", kind="refine", ms=agent.ms(started), data=data)
        self.tracer.trace(inquiry.correlation_id, event)
        return refined

    def _instructions(self, correlation_id: str) -> str:
        library = self.sql.library()
        if library.error is not None:
            raise RuntimeError(f"the library query failed: {library.error}")
        rows = json.dumps(library.rows, ensure_ascii=False, default=str)
        library_schema = self.sql.schema()
        text = agent.INSTRUCTIONS.read_text(encoding="utf-8")
        context = self.context()
        text = text.replace("{context}", context)
        text = text.replace("{rounds}", str(agent.ROUNDS))
        text = text.replace("{library}", rows)
        text = text.replace("{schema}", library_schema.model_dump_json(indent=1))
        data = {
            "prompt": agent.INSTRUCTIONS.name,
            "context": context,
            "library": json.loads(rows),
            "schema": library_schema.model_dump(mode="json"),
            "text": text,
        }
        self.tracer.trace(correlation_id, Event(step="system", kind="system", data=data))
        return text

    def _verify(self, inquiry: Inquiry) -> None:
        """A value is verified when its source's document is confirmed: read by a parser, not
        drafted by a model. A value whose source isn't in `sources` is not verified."""
        if inquiry.result is None:
            return
        documents: dict[int, int] = {}
        for source in inquiry.result.sources:
            documents[source.id] = source.document_id
        statuses = self.documents.statuses(list(documents.values()))
        marked: list[dict[str, Any]] = []
        for value in inquiry.result.values:
            document_id = documents.get(value.source)
            status = None
            if document_id is not None:
                status = statuses.get(document_id)
            value.verified = status == DocumentStatus.confirmed
            marked.append(
                {
                    "name": value.name,
                    "source": value.source,
                    "document_id": document_id,
                    "document_status": status,
                    "verified": value.verified,
                }
            )
        event = Event(step="verified", kind="verified", data={"values": marked})
        self.tracer.trace(inquiry.correlation_id, event)

    def _link(self, inquiry: Inquiry) -> None:
        """Each source gets the sizes of its section and its document, as get_section and
        get_document return them, and its file's link. A section_id not in the source's
        document becomes None, and so does every size of a document that doesn't exist."""
        if inquiry.result is None:
            return
        document_ids: list[int] = []
        for source in inquiry.result.sources:
            document_ids.append(source.document_id)
        paths = self.documents.paths(document_ids)
        linked: list[dict[str, Any]] = []
        for source in inquiry.result.sources:
            sent = source.section_id
            texts = self.documents.sections(source.document_id)
            whole = self.documents.document(source.document_id)
            source.section_id = None
            if texts is not None and whole is not None:
                source.document_chars = len(whole)
                if sent in texts:
                    source.section_id = sent
                    source.section_chars = len(texts[sent])
            source.file = self._file(paths.get(source.document_id))
            linked.append(
                {
                    "id": source.id,
                    "document_id": source.document_id,
                    "section_id_sent": sent,
                    "section_id": source.section_id,
                    "section_chars": source.section_chars,
                    "document_chars": source.document_chars,
                    "file": source.file,
                }
            )
        event = Event(step="linked", kind="linked", data={"sources": linked})
        self.tracer.trace(inquiry.correlation_id, event)

    def _file(self, path: str | None) -> str | None:
        """The file link with the path in it, quoted; None without either."""
        if self.file_url is None or path is None:
            return None
        return self.file_url.replace("{path}", quote(path))


def _totals(inquiry: Inquiry) -> dict[str, Any]:
    return {
        "input_tokens": inquiry.tokens_in,
        "output_tokens": inquiry.tokens_out,
        "rounds": inquiry.rounds,
        "calls": inquiry.calls,
    }
