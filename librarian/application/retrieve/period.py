"""A question's time filter on the documents' validity, already resolved by the caller.

Code only: a Period never reads words. `Period("during", "2026-05")` is a May 2026; the
question's "a maggio" was turned into that by someone else.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

VALUE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


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
    _day_after: date = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        try:
            op = PeriodOp(self.op)
        except ValueError:
            raise ValueError(f"unknown period op: {self.op!r}") from None
        object.__setattr__(self, "op", op)
        start, day_after = _parse(self.value)
        object.__setattr__(self, "_start", start)
        object.__setattr__(self, "_day_after", day_after)

    @property
    def start(self) -> date:
        return self._start

    @property
    def day_after(self) -> date:
        """The day after the period ends, unlike a document's validity, which ends on its
        last day."""
        return self._day_after


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
