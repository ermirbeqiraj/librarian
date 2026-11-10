"""A time filter on `documents.validity`, already resolved by the caller (the plan, task 06).

Code only: a Period never reads words. `Period("during", "2026-05")` is a May 2026; the
question's "a maggio" was turned into that by someone else.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

VALUE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
# The column name goes into SQL text; callers pass a literal like "d.validity".
COLUMN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


class PeriodOp(StrEnum):
    during = "during"  # overlaps the period
    after = "after"  # open-ended, from the period's end
    before = "before"  # open-ended, up to the period's start
    on = "on"  # contains the period's first day


@dataclass(frozen=True)
class Period:
    op: PeriodOp | str
    # A year, month or day: "2026", "2026-05", "2026-05-14".
    value: str
    _start: date = field(init=False, repr=False, compare=False)
    _end: date = field(init=False, repr=False, compare=False)  # exclusive

    def __post_init__(self) -> None:
        try:
            op = PeriodOp(self.op)
        except ValueError:
            raise ValueError(f"unknown period op: {self.op!r}") from None
        object.__setattr__(self, "op", op)
        start, end = _parse(self.value)
        object.__setattr__(self, "_start", start)
        object.__setattr__(self, "_end", end)

    @property
    def start(self) -> date:
        return self._start

    @property
    def end(self) -> date:
        """Exclusive: the day after the period ends."""
        return self._end

    def sql(self, column: str = "validity") -> tuple[str, dict[str, Any]]:
        """The predicate on a daterange column, as SQL and bound parameters."""
        if COLUMN.fullmatch(column) is None:
            raise ValueError(f"not a column name: {column!r}")
        params: dict[str, Any] = {"period_start": self._start, "period_end": self._end}
        if self.op is PeriodOp.during:
            return f"{column} && daterange(:period_start, :period_end, '[)')", params
        if self.op is PeriodOp.after:
            return f"{column} && daterange(:period_end, NULL, '[)')", params
        if self.op is PeriodOp.before:
            return f"{column} && daterange(NULL, :period_start, '[)')", params
        return f"{column} @> CAST(:period_start AS date)", {"period_start": self._start}

    def filter_sql(self, column: str = "validity") -> tuple[str, dict[str, Any]]:
        """The predicate with the null case: documents with no validity always pass."""
        if COLUMN.fullmatch(column) is None:
            raise ValueError(f"not a column name: {column!r}")
        predicate, params = self.sql(column)
        return f"({column} IS NULL OR {predicate})", params


def _parse(value: str) -> tuple[date, date]:
    """A year, month or day as a half-open [start, end) range of dates."""
    match = VALUE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"period value must be a year, month or day: {value!r}")
    year = int(match[1])
    month = match[2]
    day = match[3]
    if month is None:
        return date(year, 1, 1), date(year + 1, 1, 1)
    if day is None:
        start = date(year, int(month), 1)
        end = date(year + 1, 1, 1) if int(month) == 12 else date(year, int(month) + 1, 1)
        return start, end
    start = date(year, int(month), int(day))  # ValueError on an impossible date
    return start, start + timedelta(days=1)
