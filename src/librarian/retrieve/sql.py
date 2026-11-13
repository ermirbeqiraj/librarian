"""The agent's read-only SQL tool: run one query as `librarian_reader`, see the schema.

The connection is set up once at startup from `LIBRARIAN_READER_DATABASE_URL` and speaks
only as the `librarian_reader` role (provisioned outside the app: by infra on a managed
cluster, by the test setup in dev — no migration creates roles): read-only, one 5 s
statement, SELECT on `documents` and `document_sections` only. A bad query fails at the
database and comes back as an error the agent can read; the worst it can do is return
wrong rows.
"""

import atexit
import json
import threading
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, LiteralString, cast

import psycopg
from psycopg import sql
from psycopg.types.json import set_json_loads
from psycopg.types.range import Range
from pydantic import BaseModel, ConfigDict

from librarian.config import READER_DATABASE_URL

MAX_ROWS = 200
TOO_MANY_ROWS = "too many rows: aggregate in SQL or add a LIMIT"
# Our own clock, outside the session: the role's 5 s statement_timeout is a default the
# agent's SQL can switch off (set_config), this one it can't. A bit later than 5 s, so
# the database's own timeout normally fires first.
CANCEL_SECONDS = 8
CANCELLED = f"stopped after {CANCEL_SECONDS} s: make the query cheaper"

_CONNINFO = READER_DATABASE_URL.replace("+psycopg", "")
_connection: psycopg.Connection | None = None


def reader_connection() -> psycopg.Connection:
    """The one connection the tool uses, opened on first use and kept for the process."""
    global _connection
    if _connection is None or _connection.closed:
        _connection = psycopg.connect(_CONNINFO)
        # JSON numbers as Decimal, like the app's own engine: amounts stay exact.
        set_json_loads(_loads_with_decimals, _connection)
    return _connection


def _loads_with_decimals(data: str | bytes) -> Any:
    return json.loads(data, parse_float=Decimal)


def _close() -> None:
    if _connection is not None:
        _connection.close()


atexit.register(_close)


class SqlResult(BaseModel):
    """One query's outcome: `rows` (with `columns`), or the database's `error`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    error: str | None = None


def run_sql(query: str) -> SqlResult:
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
        connection = reader_connection()

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


EXAMPLES: list[str] = [
    # Check the connection.
    "SELECT 1",
    # Count documents per kind.
    """SELECT kind, count(*) AS documents
FROM documents
GROUP BY kind
ORDER BY documents DESC""",
    # The latest gas bill and its total.
    """SELECT id, validity, fields ->> 'total_amount' AS total_amount
FROM documents
WHERE kind = 'invoice' AND fields ->> 'service' = 'gas'
ORDER BY lower(validity) DESC
LIMIT 1""",
    # Water spent in 2025: a sum over a date range on validity.
    """SELECT sum((fields ->> 'total_amount')::numeric) AS spent_2025
FROM documents
WHERE fields ->> 'service' = 'water'
  AND validity && daterange('2025-01-01', '2026-01-01', '[)')""",
    # One value out of `fields`, cast to a number.
    """SELECT id, (fields ->> 'total_amount')::numeric AS total_amount
FROM documents
WHERE fields ? 'total_amount'
ORDER BY lower(validity) DESC
LIMIT 10""",
]

_EXAMPLES_SQL = "\n\n".join(f"```sql\n{example}\n```" for example in EXAMPLES)

SQL_TOOL_DESCRIPTION = f"""Run one SQL query against the library database and read the rows.

What you can see (call schema() for the columns and the most used `fields` keys):
- documents(id, ingestion_id, kind, validity, fields, parser, description, problems, status, created_at)
- document_sections(id, document_id, position, heading, text, created_at)

`fields` is a JSON object: its keys are not columns. Read a value with fields ->> 'key',
test for a key with fields ? 'key'. `validity` is a date range stored as [start, end):
lower(validity) is the first day, upper(validity) the day after the last one. In the
rows it comes back as {{start, end}} with end the last day. validity &&
daterange('2025-01-01', '2026-01-01') matches the year 2025.

Only a query runs: SELECT, WITH ... SELECT, VALUES or TABLE. Writes, SET, SHOW and
EXPLAIN fail at the database.

Limits: the connection is read-only, writes fail at the database; each statement stops
after 5 seconds; a query returning more than 200 rows is an error, aggregate in SQL or
add a LIMIT.

Examples, from simple to hard:

{_EXAMPLES_SQL}
"""
