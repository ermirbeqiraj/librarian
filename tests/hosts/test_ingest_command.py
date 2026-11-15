import os
import sys
import threading
from pathlib import Path

import pytest

import librarian.hosts.ingest as ingest_main
from librarian.adapters.inbox import FolderInbox
from librarian.application.ingest.pipeline import Pipeline
from librarian.hosts import wiring


@pytest.fixture
def processed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    """The command on an inbox under tmp_path, run with --once; each file it processes is
    only named in the list it returns."""
    processed: list[str] = []
    pipeline = Pipeline(None, None, None, None, None, FolderInbox(tmp_path))
    monkeypatch.setattr(pipeline, "process", lambda path: processed.append(path.name))
    monkeypatch.setattr(wiring, "pipeline", lambda: pipeline)
    monkeypatch.setattr(sys, "argv", ["librarian-ingest", "--once"])
    return processed


@pytest.fixture
def inbox(tmp_path: Path) -> Path:
    return tmp_path / "inbox"


def settled(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-")
    os.utime(path, (0, 0))


def no_sleep(seconds: float) -> None:
    raise AssertionError("slept")


def test_once_processes_the_inbox_and_exits(
    monkeypatch: pytest.MonkeyPatch, processed: list[str], inbox: Path
) -> None:
    monkeypatch.setattr(ingest_main.time, "sleep", no_sleep)
    settled(inbox / "a.pdf")
    settled(inbox / "b.pdf")
    ingest_main.main()
    assert processed == ["a.pdf", "b.pdf"]


def test_once_with_an_empty_inbox_exits_at_once(
    monkeypatch: pytest.MonkeyPatch, processed: list[str]
) -> None:
    monkeypatch.setattr(ingest_main.time, "sleep", no_sleep)
    ingest_main.main()


def test_once_waits_for_a_file_still_being_written(
    monkeypatch: pytest.MonkeyPatch, processed: list[str], inbox: Path
) -> None:
    path = inbox / "a.pdf"
    inbox.mkdir()
    path.write_bytes(b"%PDF-")
    monkeypatch.setattr(ingest_main.time, "sleep", lambda seconds: settled(path))
    ingest_main.main()
    assert processed == ["a.pdf"]


def test_without_once_it_watches_until_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    stop_requested = threading.Event()
    passes: list[int] = []

    class Counted:
        def ingest_once(self) -> bool:
            passes.append(1)
            if len(passes) == 3:
                stop_requested.set()
            return False

    monkeypatch.setattr(sys, "argv", ["librarian-ingest"])
    monkeypatch.setattr(ingest_main, "stop_requested", stop_requested)
    monkeypatch.setattr(wiring, "pipeline", Counted)
    monkeypatch.setattr(ingest_main, "POLL_SECONDS", 0)
    monkeypatch.setattr(ingest_main.signal, "signal", lambda signum, handler: None)
    ingest_main.main()
    assert len(passes) == 3
