import signal
import threading
from types import FrameType

from librarian.config import POLL_SECONDS
from librarian.ingest.pipeline import ingest_once

stop_requested = threading.Event()


def stop(signum: int, frame: FrameType | None) -> None:
    stop_requested.set()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stop_requested.is_set():
        ingest_once()
        stop_requested.wait(POLL_SECONDS)


if __name__ == "__main__":
    main()
