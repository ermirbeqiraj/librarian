from pathlib import Path

import pytest

from librarian.hosts import config, wiring


def test_the_context_is_the_hand_written_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config, "ROOT", tmp_path)
    assert wiring.context() == ""
    (tmp_path / "context.md").write_text("Anna è la figlia.\n")
    assert wiring.context() == "Anna è la figlia."
