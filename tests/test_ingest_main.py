import os
import sys
import threading
from pathlib import Path

import pytest

import librarian.ingest.__main__ as ingest_main
from librarian.ingest import pipeline


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(pipeline, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["librarian-ingest", "--once"])
    return tmp_path


def settled(path: Path) -> None:
    path.write_bytes(b"%PDF-")
    os.utime(path, (0, 0))


def no_sleep(seconds: float) -> None:
    raise AssertionError("slept")


def test_once_processes_the_inbox_and_exits(monkeypatch: pytest.MonkeyPatch, inbox: Path) -> None:
    processed: list[str] = []
    monkeypatch.setattr(pipeline, "process", lambda path: processed.append(path.name))
    monkeypatch.setattr(ingest_main.time, "sleep", no_sleep)
    settled(inbox / "a.pdf")
    settled(inbox / "b.pdf")
    ingest_main.main()
    assert processed == ["a.pdf", "b.pdf"]


def test_once_with_an_empty_inbox_exits_at_once(
    monkeypatch: pytest.MonkeyPatch, inbox: Path
) -> None:
    monkeypatch.setattr(ingest_main.time, "sleep", no_sleep)
    ingest_main.main()


def test_once_waits_for_a_file_still_being_written(
    monkeypatch: pytest.MonkeyPatch, inbox: Path
) -> None:
    processed: list[str] = []
    monkeypatch.setattr(pipeline, "process", lambda path: processed.append(path.name))
    path = inbox / "a.pdf"
    path.write_bytes(b"%PDF-")
    monkeypatch.setattr(ingest_main.time, "sleep", lambda seconds: settled(path))
    ingest_main.main()
    assert processed == ["a.pdf"]


def test_without_once_it_watches_until_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    stop_requested = threading.Event()
    passes: list[int] = []

    def ingest_once() -> bool:
        passes.append(1)
        if len(passes) == 3:
            stop_requested.set()
        return False

    monkeypatch.setattr(sys, "argv", ["librarian-ingest"])
    monkeypatch.setattr(ingest_main, "stop_requested", stop_requested)
    monkeypatch.setattr(ingest_main, "ingest_once", ingest_once)
    monkeypatch.setattr(ingest_main, "POLL_SECONDS", 0)
    monkeypatch.setattr(ingest_main.signal, "signal", lambda signum, handler: None)
    ingest_main.main()
    assert len(passes) == 3
