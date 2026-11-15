"""The agent's read-only SQL tool: run one query as `librarian_reader`, see the schema.

Each thread's connection speaks only as the `librarian_reader` role (provisioned outside the
app: by infra on a managed cluster, by the test setup in dev — no migration creates roles):
read-only, one 5 s statement, SELECT on `documents` and `document_sections` only. A bad query
fails at the database and comes back as an error the agent can read; the worst it can do is
return wrong rows.
"""

import atexit
import json
import threading
import weakref
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, LiteralString, cast

import psycopg
from psycopg import sql
from psycopg.types.json import set_json_loads
from psycopg.types.range import Range

from librarian.application.retrieve.ports import Column, FieldKey, Schema, SqlResult, Table

MAX_ROWS = 200
TOO_MANY_ROWS = "too many rows: aggregate in SQL or add a LIMIT"
# Our own clock, outside the session: the role's 5 s statement_timeout is a default the
# agent's SQL can switch off (set_config), this one it can't. A bit later than 5 s, so
# the database's own timeout normally fires first.
CANCEL_SECONDS = 8
CANCELLED = f"stopped after {CANCEL_SECONDS} s: make the query cheaper"

LIBRARY_SQL = """SELECT kind, fields ->> 'issuer' AS issuer, count(*) AS documents,
       min(lower(validity)) AS first, max(upper(validity)) AS last
FROM documents GROUP BY 1, 2 ORDER BY 1, 2"""

FIELD_KEY_LIMIT = 100

_TABLES_SQL = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
"""

# One row per key of `fields`: how many documents have it, the kinds they are, one
# example value (from the newest document: jsonb has no min()). Only the FIELD_KEY_LIMIT
# most used keys.
_FIELDS_SQL = f"""
    SELECT key,
           count(*) AS document_count,
           array_agg(DISTINCT d.kind ORDER BY d.kind) AS kinds,
           (array_agg(d.fields -> key ORDER BY d.id DESC))[1] AS example
    FROM documents d
    CROSS JOIN LATERAL jsonb_object_keys(d.fields) AS k(key)
    GROUP BY key
    ORDER BY document_count DESC, key
    LIMIT {FIELD_KEY_LIMIT}
"""


class ReaderConnections:
    """One connection per thread, opened on first use and kept for the thread: the MCP server
    reads from several threads at once, and a transaction or a cancel on a shared connection
    would land on another thread's query. Every one still open is closed at exit."""

    def __init__(self, url: str) -> None:
        self.conninfo = url.replace("+psycopg", "")
        self._local = threading.local()
        self._open: weakref.WeakSet[psycopg.Connection] = weakref.WeakSet()
        self._open_lock = threading.Lock()
        atexit.register(self._close)

    def get(self) -> psycopg.Connection:
        """This thread's connection."""
        connection: psycopg.Connection | None = getattr(self._local, "connection", None)
        if connection is None or connection.closed:
            connection = psycopg.connect(self.conninfo)
            # JSON numbers as Decimal, like the app's own engine: amounts stay exact.
            set_json_loads(_loads_with_decimals, connection)
            self._local.connection = connection
            with self._open_lock:
                self._open.add(connection)
        return connection

    def _close(self) -> None:
        with self._open_lock:
            for connection in list(self._open):
                connection.close()


def _loads_with_decimals(data: str | bytes) -> Any:
    return json.loads(data, parse_float=Decimal)


class PostgresSql:
    def __init__(self, connections: ReaderConnections) -> None:
        self.connections = connections
        self._schema: Schema | None = None

    def run_sql(self, query: str) -> SqlResult:
        """Run one query as `librarian_reader`.

        The role's read-only and 5 s settings are only defaults the session can change, so:
        - one statement per call: it goes through a prepared statement, and Postgres refuses
          to prepare more than one command ("SET statement_timeout = 0; SELECT ..." fails);
        - every call is rolled back, never committed: a SET dies with its call and never
          reaches the next one on this long-lived connection;
        - our code cancels the query after CANCEL_SECONDS, whatever the session has set.

        Every query is wrapped as `SELECT * FROM (<query>) AS q LIMIT MAX_ROWS + 1`, so
        Postgres itself stops at the cap and a runaway SELECT never reaches memory (libpq
        buffers a whole result); more than MAX_ROWS rows comes back as the cap error. No
        guessing from the first word ("/* */ SELECT" fooled that): what can't be a subquery
        (writes, SET, SHOW, EXPLAIN) fails at the database.
        """
        timer: threading.Timer | None = None
        cancelled = threading.Event()
        try:
            connection = self.connections.get()

            def cancel() -> None:
                cancelled.set()
                connection.cancel_safe()

            timer = threading.Timer(CANCEL_SECONDS, cancel)
            timer.start()
            with connection.transaction(force_rollback=True), connection.cursor() as cursor:
                cursor.execute(raw_sql(wrapped(query)), prepare=True)
                result = _collect(cursor)
        except Exception as error:  # noqa: BLE001 - the agent reads this, it is not a crash
            if cancelled.is_set():
                return SqlResult(error=CANCELLED)
            return SqlResult(error=_message(error))
        finally:
            # Stop the timer and wait for it, so a late cancel can't hit the next call.
            if timer is not None:
                timer.cancel()
                timer.join()
        if len(result.rows) > MAX_ROWS:
            return SqlResult(error=TOO_MANY_ROWS)
        return result

    def schema(self) -> Schema:
        """The visible tables with their columns and types, and the top `FIELD_KEY_LIMIT`
        keys of `fields` with their document count, kinds and one example value. Read once
        and kept: the agent never writes schema queries itself. As `librarian_reader`,
        `information_schema` already hides everything the agent cannot read."""
        if self._schema is None:
            self._schema = self._load_schema()
        return self._schema

    def _load_schema(self) -> Schema:
        connection = self.connections.get()
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

    def library(self) -> SqlResult:
        return self.run_sql(LIBRARY_SQL)


def wrapped(query: str) -> str:
    """The agent's query as a subquery capped at MAX_ROWS + 1 rows. Trailing semicolons
    go (they can't sit inside the parentheses); the closing parenthesis gets its own line,
    so a trailing `-- comment` can't swallow it."""
    body = query.strip()
    while body.endswith(";"):
        body = body[:-1].rstrip()
    return f"SELECT * FROM (\n{body}\n) AS q LIMIT {MAX_ROWS + 1}"


def raw_sql(query: str) -> sql.SQL:
    """The agent's SQL goes in raw; psycopg types want a literal, the reader role is
    the guard, not the type."""
    return sql.SQL(cast(LiteralString, query))


def _collect(cursor: psycopg.Cursor[Any]) -> SqlResult:
    if cursor.description is None:
        return SqlResult()
    columns = [column.name for column in cursor.description]
    # Rows are dicts by column name: a repeated name would silently drop a value.
    seen: set[str] = set()
    for name in columns:
        if name in seen:
            return SqlResult(error=f"two columns are named {name!r}: name them apart with AS")
        seen.add(name)
    rows = [
        {name: _jsonable(value) for name, value in zip(columns, row, strict=True)}
        for row in cursor.fetchmany(MAX_ROWS + 1)
    ]
    return SqlResult(columns=columns, rows=rows)


def _message(error: Exception) -> str:
    if isinstance(error, psycopg.Error):
        return error.diag.message_primary or str(error)
    return str(error)


def _jsonable(value: Any) -> Any:
    """SQL values in the shapes the agent reads: amounts as exact numbers (Decimal),
    dates and times as ISO text, a range as {"start", "end"}, the rest as its text."""
    if value is None or isinstance(value, (bool, int, float, str, Decimal)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Range):
        return {"start": _jsonable(value.lower), "end": _jsonable(_last_day(value))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return str(value)


def _last_day(value: Range) -> Any:
    """The range's inclusive end. Postgres stores a daterange as [start, end), so a
    bill for March comes back with upper = 1 April; the agent reads 31 March."""
    upper = value.upper
    if isinstance(upper, date) and not isinstance(upper, datetime) and not value.upper_inc:
        return upper - timedelta(days=1)
    return upper
