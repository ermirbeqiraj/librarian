import argparse

from librarian.retrieve.ask import ask


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask one question and print what it went through.")
    parser.add_argument("question")
    parser.add_argument("--model", required=True, help="the agent's model")
    args = parser.parse_args()
    print(ask(args.question, args.model).model_dump_json(indent=2, by_alias=True))


if __name__ == "__main__":
    main()
