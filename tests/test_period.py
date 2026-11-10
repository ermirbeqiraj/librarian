from datetime import date

import pytest
from sqlalchemy.dialects.postgresql import Range

from librarian.retrieve.period import Period, PeriodOp
from librarian.retrieve.search import search


def test_year_month_day_values() -> None:
    assert (Period("during", "2026").start, Period("during", "2026").end) == (
        date(2026, 1, 1),
        date(2027, 1, 1),
    )
    assert (Period("during", "2026-05").start, Period("during", "2026-05").end) == (
        date(2026, 5, 1),
        date(2026, 6, 1),
    )
    assert (Period("on", "2026-05-14").start, Period("on", "2026-05-14").end) == (
        date(2026, 5, 14),
        date(2026, 5, 15),
    )
    assert Period("during", "2026-12").end == date(2027, 1, 1)


def test_bad_values_raise() -> None:
    for value in ["14/05/2026", "2026-13", "2026-05-32", "maggio 2026", ""]:
        with pytest.raises(ValueError):
            Period("during", value)
    with pytest.raises(ValueError):
        Period("in", "2026")


def test_op_is_an_enum_member() -> None:
    assert Period("during", "2026").op is PeriodOp.during
    assert Period("during", "2026") == Period(PeriodOp.during, "2026")


def test_the_four_ops_and_null_validity(add_document) -> None:
    may = add_document(
        validity=Range(date(2026, 5, 1), date(2026, 6, 1), bounds="[)"),
        sections=[("Bolletta", "bolletta di maggio", [("Bolletta\nbolletta di maggio", 0)])],
    )
    year = add_document(
        validity=Range(date(2026, 1, 1), date(2027, 1, 1), bounds="[)"),
        sections=[("Bolletta", "bolletta dell anno", [("Bolletta\nbolletta dell anno", 1)])],
    )
    timeless = add_document(
        validity=None,
        sections=[("Bolletta", "bolletta senza date", [("Bolletta\nbolletta senza date", 2)])],
    )
    all_three = {may.id, year.id, timeless.id}

    def ids(period: Period) -> set[int | None]:
        return {hit.document_id for hit in search("bolletta", period=period, mode="keyword")}

    assert ids(Period("during", "2026-05")) == all_three
    assert ids(Period("during", "2026-06")) == {year.id, timeless.id}
    assert ids(Period("after", "2026-05")) == {year.id, timeless.id}
    assert ids(Period("before", "2026-05")) == {year.id, timeless.id}
    assert ids(Period("on", "2026-05-14")) == all_three
    assert ids(Period("on", "2025-06-15")) == {timeless.id}
