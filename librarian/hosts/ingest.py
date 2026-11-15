import argparse
import signal
import threading
import time
from types import FrameType

from librarian.hosts import wiring

POLL_SECONDS = 10

stop_requested = threading.Event()


def stop(signum: int, frame: FrameType | None) -> None:
    stop_requested.set()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest what lands in the inbox, until stopped.")
    parser.add_argument(
        "--once", action="store_true", help="process what is in the inbox, then exit"
    )
    args = parser.parse_args()
    pipeline = wiring.pipeline()
    if args.once:
        while pipeline.ingest_once():
            time.sleep(POLL_SECONDS)
        return
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stop_requested.is_set():
        pipeline.ingest_once()
        stop_requested.wait(POLL_SECONDS)


if __name__ == "__main__":
    main()
