"""The schema the agent sees: the visible tables and the top keys of `documents.fields`.

Two fixed queries, written here, run once and kept in memory: the agent calls schema(),
it never writes schema queries itself. They run as `librarian_reader`, so
`information_schema` already hides everything the agent cannot read.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from librarian.retrieve.sql import _jsonable, raw_sql, reader_connection

FIELD_KEY_LIMIT = 100

_TABLES_SQL = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
"""

# One row per key of `fields`: how many documents have it, the kinds they are, one
# example value. Only the FIELD_KEY_LIMIT most used keys.
_FIELDS_SQL = f"""
    SELECT key,
           count(*) AS document_count,
           array_agg(DISTINCT d.kind ORDER BY d.kind) AS kinds,
           min(d.fields -> key) AS example
    FROM documents d
    CROSS JOIN LATERAL jsonb_object_keys(d.fields) AS k(key)
    GROUP BY key
    ORDER BY document_count DESC, key
    LIMIT {FIELD_KEY_LIMIT}
"""


class Column(BaseModel):
    name: str
    type: str


class Table(BaseModel):
    name: str
    columns: list[Column]


class FieldKey(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str
    document_count: int
    kinds: list[str]
    example: Any


class Schema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tables: list[Table]
    field_keys: list[FieldKey]


_cache: Schema | None = None


def schema() -> Schema:
    """The visible tables with their columns and types, and the top `FIELD_KEY_LIMIT`
    keys of `fields` with their document count, kinds and one example value."""
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def _load() -> Schema:
    connection = reader_connection()
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(raw_sql(_TABLES_SQL))
        tables: dict[str, Table] = {}
        for table_name, column_name, data_type in cursor.fetchall():
            table = tables.setdefault(table_name, Table(name=table_name, columns=[]))
            table.columns.append(Column(name=column_name, type=data_type))
        cursor.execute(raw_sql(_FIELDS_SQL))
        field_keys = [
            FieldKey(
                key=key,
                document_count=document_count,
                kinds=list(kinds),
                example=_jsonable(example),
            )
            for key, document_count, kinds, example in cursor.fetchall()
        ]
    return Schema(tables=list(tables.values()), field_keys=field_keys)
