from librarian.application.ingest.drafter.drafter import INSTRUCTIONS, instructions_text
from librarian.application.ingest.kinds import FIELDS


def test_the_prompt_names_each_kinds_fields() -> None:
    lines = instructions_text(INSTRUCTIONS).splitlines()
    for kind, names in FIELDS.items():
        start = lines.index(f"- {kind}:") + 1
        for offset, name in enumerate(names):
            assert lines[start + offset].startswith(f"  - {name}: ")
