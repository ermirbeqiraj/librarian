"""The SQL tool, against the `librarian_test` database (skipped when it is unreachable).

The tool connects as `librarian_reader`, the role the migration creates with grants on
`documents` and `document_sections` only, so these tests prove the borders at the
database: writes fail, hidden tables are not readable, 5 s stops pg_sleep, 200 rows cap.
"""

import re
import time
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.dialects.postgresql import Range

import librarian.retrieve.schema as schema_module
from librarian.retrieve.schema import schema
from librarian.retrieve.sql import MAX_ROWS, SQL_TOOL_DESCRIPTION, TOO_MANY_ROWS, run_sql


@pytest.fixture
def fresh_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop schema()'s in-memory cache, so each test sees the documents it seeded."""
    monkeypatch.setattr(schema_module, "_cache", None)


def test_select_runs_and_returns_rows(test_db: None) -> None:
    result = run_sql("SELECT 1 AS one")
    assert result.error is None
    assert result.columns == ["one"]
    assert result.rows == [{"one": 1}]


@pytest.mark.parametrize(
    "query",
    [
        (
            "INSERT INTO documents (ingestion_id, kind, fields, problems, status)"
            " VALUES (1, 'invoice', '{}', '[]', 'confirmed')"
        ),
        "UPDATE documents SET kind = 'other'",
        "DELETE FROM documents",
        "CREATE TABLE agent_notes (id int)",
        "RESET ROLE; DELETE FROM documents",
    ],
)
def test_writes_fail_at_the_database(test_db: None, query: str) -> None:
    result = run_sql(query)
    assert result.error is not None
    assert result.rows == []
    assert result.columns == []


@pytest.mark.parametrize("query", ["SELECT * FROM ingestions", "SELECT * FROM chunks"])
def test_ingestions_and_chunks_cannot_be_read(test_db: None, query: str) -> None:
    result = run_sql(query)
    assert result.error is not None
    assert "permission denied" in result.error


def test_pg_sleep_stops_at_5_seconds_with_a_readable_error(test_db: None) -> None:
    started = time.monotonic()
    result = run_sql("SELECT pg_sleep(10)")
    elapsed = time.monotonic() - started
    assert result.error is not None
    assert "statement timeout" in result.error
    assert elapsed < 8


def test_more_than_200_rows_is_the_cap_error(add_document) -> None:
    for _ in range(MAX_ROWS + 1):
        add_document()
    result = run_sql("SELECT id FROM documents")
    assert result.error == TOO_MANY_ROWS
    assert result.rows == []


def test_200_rows_come_back(add_document) -> None:
    for _ in range(MAX_ROWS):
        add_document()
    result = run_sql("SELECT id FROM documents")
    assert result.error is None
    assert len(result.rows) == MAX_ROWS


def test_amounts_dates_and_ranges_come_back_in_shape(add_document) -> None:
    document = add_document(
        validity=Range(date(2025, 3, 1), date(2025, 3, 31), bounds="[]"),
        fields={"issuer": "Cogeide S.p.A.", "service": "water", "total_amount": "41.20"},
    )
    result = run_sql(
        "SELECT (fields ->> 'total_amount')::numeric AS amount, "
        f"lower(validity) AS day, validity FROM documents WHERE id = {document.id}"
    )
    assert result.error is None
    (row,) = result.rows
    assert isinstance(row["amount"], Decimal)
    assert row["amount"] == Decimal("41.20")
    assert row["day"] == "2025-03-01"
    assert row["validity"] == {"start": "2025-03-01", "end": "2025-03-31"}


def test_schema_lists_only_the_visible_tables_and_their_columns(
    test_db: None, fresh_schema: None
) -> None:
    result = schema()
    tables = {table.name: table for table in result.tables}
    assert set(tables) == {"documents", "document_sections"}
    columns = {column.name: column.type for column in tables["documents"].columns}
    assert columns["fields"] == "jsonb"
    assert columns["validity"] == "daterange"
    assert {"id", "kind", "status", "created_at"} <= set(columns)
    section_columns = {column.name for column in tables["document_sections"].columns}
    assert {"id", "document_id", "heading", "text"} <= section_columns


def test_schema_lists_field_keys_with_count_kinds_and_example(
    add_document, fresh_schema: None
) -> None:
    add_document(
        kind="invoice",
        fields={"issuer": "Hera S.p.A.", "service": "gas", "total_amount": "63.33"},
    )
    add_document(kind="invoice", fields={"issuer": "Cogeide S.p.A.", "service": "water"})
    add_document(kind="contract", fields={"issuer": "Controparte S.p.A."})
    keys = {field_key.key: field_key for field_key in schema().field_keys}
    assert keys["issuer"].document_count == 3
    assert keys["issuer"].kinds == ["contract", "invoice"]
    assert keys["issuer"].example in {"Hera S.p.A.", "Cogeide S.p.A.", "Controparte S.p.A."}
    assert keys["service"].document_count == 2
    assert keys["service"].kinds == ["invoice"]
    assert keys["service"].example in {"gas", "water"}
    assert keys["total_amount"].document_count == 1
    assert keys["total_amount"].example == 63.33


def test_schema_returns_only_the_top_100_field_keys(add_document, fresh_schema: None) -> None:
    fields = {f"key_{i:03d}": i for i in range(105)}
    fields["common"] = "x"
    add_document(fields=fields)
    add_document(fields={"common": "y", "issuer": "Test S.p.A."})
    field_keys = schema().field_keys
    assert len(field_keys) == 100
    keys = {field_key.key for field_key in field_keys}
    # "common" is on two documents, so it is the most used key and stays.
    assert field_keys[0].key == "common"
    assert field_keys[0].document_count == 2
    assert "issuer" in keys


def _examples() -> list[str]:
    return [
        match.strip() for match in re.findall(r"```sql\n(.*?)```", SQL_TOOL_DESCRIPTION, re.DOTALL)
    ]


def test_every_example_in_the_tool_description_runs_and_returns_rows(add_document) -> None:
    add_document(
        kind="invoice",
        validity=Range(date(2025, 1, 1), date(2025, 1, 31), bounds="[]"),
        fields={"issuer": "Hera S.p.A.", "service": "gas", "total_amount": "63.33"},
    )
    add_document(
        kind="invoice",
        validity=Range(date(2025, 6, 1), date(2025, 6, 30), bounds="[]"),
        fields={"issuer": "Cogeide S.p.A.", "service": "water", "total_amount": "41.20"},
    )
    add_document(
        kind="invoice",
        validity=Range(date(2026, 2, 1), date(2026, 2, 28), bounds="[]"),
        fields={"issuer": "Hera S.p.A.", "service": "gas", "total_amount": "70.00"},
    )
    examples = _examples()
    assert len(examples) == 5
    for example in examples:
        result = run_sql(example)
        assert result.error is None, example
        assert result.rows, example
