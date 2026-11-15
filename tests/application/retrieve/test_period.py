from datetime import date

import pytest

from librarian.application.retrieve.period import Period, PeriodOp


def test_year_month_day_values() -> None:
    assert (Period("during", "2026").start, Period("during", "2026").day_after) == (
        date(2026, 1, 1),
        date(2027, 1, 1),
    )
    assert (Period("during", "2026-05").start, Period("during", "2026-05").day_after) == (
        date(2026, 5, 1),
        date(2026, 6, 1),
    )
    assert (Period("on", "2026-05-14").start, Period("on", "2026-05-14").day_after) == (
        date(2026, 5, 14),
        date(2026, 5, 15),
    )
    assert Period("during", "2026-12").day_after == date(2027, 1, 1)


def test_bad_values_raise() -> None:
    for value in ["14/05/2026", "2026-13", "2026-05-32", "maggio 2026", ""]:
        with pytest.raises(ValueError):
            Period("during", value)
    with pytest.raises(ValueError):
        Period("in", "2026")


def test_op_is_an_enum_member() -> None:
    assert Period("during", "2026").op is PeriodOp.during
    assert Period("during", "2026") == Period(PeriodOp.during, "2026")
