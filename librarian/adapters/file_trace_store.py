"""Every ask's trace in files: one .jsonl per run."""

from pathlib import Path

from librarian.application.retrieve.ports import Event


class FileStore:
    """<directory>/<correlation id>.jsonl, one event per line."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, correlation_id: str, events: list[Event]) -> None:
        """All of the batch or none of it: a write cut short (disk full) is truncated
        away, so the retry doesn't repeat lines."""
        text = ""
        for event in events:
            text += event.model_dump_json() + "\n"
        data = text.encode("utf-8")
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._path(correlation_id).open("ab", buffering=0) as file:
            start = file.tell()
            try:
                written = file.write(data)
                if written != len(data):
                    raise OSError(f"wrote {written} of {len(data)} bytes")
            except OSError:
                file.truncate(start)
                raise

    def read(self, correlation_id: str) -> list[Event]:
        path = self._path(correlation_id)
        events: list[Event] = []
        if not path.exists():
            return events
        for line in path.read_text(encoding="utf-8").splitlines():
            events.append(Event.model_validate_json(line))
        return events

    def _path(self, correlation_id: str) -> Path:
        return self.directory / f"{correlation_id}.jsonl"
