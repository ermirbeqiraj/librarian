"""The application imports nothing from adapters/ or hosts/, and nothing of the database:
the pipes and the plumbing stay outside what matters."""

import ast
from pathlib import Path

import librarian.application

FORBIDDEN = ("librarian.adapters", "librarian.hosts", "sqlalchemy", "psycopg")


def forbidden_imports(path: Path) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names: list[str] = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
        for name in names:
            for prefix in FORBIDDEN:
                if name == prefix or name.startswith(prefix + "."):
                    found.append(f"{path.name}:{node.lineno} imports {name}")
    return found


def test_the_application_imports_no_adapter_host_or_database() -> None:
    root = Path(librarian.application.__file__).parent
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        found.extend(forbidden_imports(path))
    assert found == []


def test_the_rule_catches_an_import_of_sqlalchemy(tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text("from sqlalchemy.dialects.postgresql import Range\n")
    assert forbidden_imports(planted) == ["planted.py:1 imports sqlalchemy.dialects.postgresql"]
