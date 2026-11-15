import argparse
import sys
from datetime import datetime
from uuid import uuid4

from librarian.retrieve.ask import ask


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask one question and print what comes back.")
    parser.add_argument("question")
    parser.add_argument("--model", required=True, help="the agent's model")
    args = parser.parse_args()
    # When it started, plus a random suffix: sorts by time, unique within a second.
    correlation_id = f"ask-{datetime.now():%Y-%m-%dT%H-%M-%S}-{uuid4().hex[:6]}"
    # First, and on stderr: a run that fails still names its trace, and stdout stays JSON.
    print(correlation_id, file=sys.stderr)
    inquiry = ask(args.question, args.model, correlation_id)
    print(inquiry.model_dump_json(indent=2, by_alias=True))


if __name__ == "__main__":
    main()
