import resource
import signal
from pathlib import Path

import pytest

from librarian.adapters.file_trace_store import FileStore
from librarian.application.retrieve.ports import Event


def started() -> Event:
    data = {
        "question": "q",
        "agent_model": "fake",
        "refine_model": "fake",
        "reasoning": "high",
        "prompt": "dig.md",
        "git_sha": None,
    }
    return Event(step="started", kind="started", data=data)


def test_a_file_write_cut_short_leaves_nothing_to_repeat(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    store.write("run-7", [started()])
    path = tmp_path / "run-7.jsonl"
    size = path.stat().st_size
    system = Event(step="system", kind="system", data={"text": "x" * 10_000})
    # Past the file size limit the kernel writes short; ignored, SIGXFSZ won't kill pytest.
    handler = signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (size + 100, hard))
    try:
        with pytest.raises(OSError):
            store.write("run-7", [system])
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
        signal.signal(signal.SIGXFSZ, handler)
    assert path.stat().st_size == size
    assert len(store.read("run-7")) == 1
