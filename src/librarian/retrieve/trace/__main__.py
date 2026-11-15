import argparse
import json
from typing import Any

from librarian.retrieve.trace import tracer

# Without --full, each value shows this many lines, each cut at WIDTH characters.
LINES = 4
WIDTH = 160


def main() -> None:
    parser = argparse.ArgumentParser(description="Print one ask's trace as an indented tree.")
    parser.add_argument("correlation_id")
    parser.add_argument("--full", action="store_true", help="print long text and outputs whole")
    args = parser.parse_args()
    events = tracer.store.read(args.correlation_id)
    if not events:
        raise SystemExit(f"no trace for {args.correlation_id}")
    print(f"{args.correlation_id} · {events[0].at}")
    current: int | None = None
    for event in events:
        indent = "  "
        title = event.step
        if event.round is not None:
            if event.round != current:
                print(f"  round {event.round}")
                current = event.round
            indent = "    "
            title = event.kind
        if event.ms is not None:
            title += f" ({event.ms} ms)"
        print(indent + title)
        for key, value in event.data.items():
            for line in _shown(key, value, args.full):
                print(f"{indent}  {line}")


def _shown(key: str, value: Any, full: bool) -> list[str]:
    text = value
    if not isinstance(value, str):
        text = json.dumps(value, ensure_ascii=False, indent=1, default=str)
    lines = f"{key}: {text}".splitlines()
    if full:
        return lines
    shown: list[str] = []
    for line in lines[:LINES]:
        if len(line) > WIDTH:
            line = line[:WIDTH] + "…"
        shown.append(line)
    if len(lines) > LINES:
        shown.append(f"… {len(lines) - LINES} more lines")
    return shown


if __name__ == "__main__":
    main()
