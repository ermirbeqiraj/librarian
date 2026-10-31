from decimal import Decimal

from librarian.evals.retrieval.matching import contains_quote, parse_number, same_value
from librarian.retrieve.result import Passage, Value


def value(written: Decimal | str, unit: str | None = None) -> Value:
    return Value(name="total", value=written, unit=unit, verified=False, source=1)


def test_amount_written_in_any_way() -> None:
    expected = Decimal("41.27")
    assert same_value(expected, "EUR", value("41,27 €"))
    assert same_value(expected, "EUR", value("41.27"))
    assert same_value(expected, "EUR", value("41.27 EUR"))
    assert same_value(expected, "EUR", value("€ 41,27"))
    assert same_value(expected, "EUR", value(Decimal("41.270"), "EUR"))


def test_amount_must_be_equal() -> None:
    assert not same_value(Decimal("41.27"), "EUR", value("41,28 €"))


def test_thousands_separators() -> None:
    assert parse_number("2.315,40") == Decimal("2315.40")
    assert parse_number("2,315.40") == Decimal("2315.40")
    assert parse_number("98.000") == Decimal(98000)


def test_units_converted_first() -> None:
    assert same_value(Decimal(98), "mc", value("98000 litri"))
    assert same_value(Decimal(98), "mc", value(Decimal(98000), "l"))
    assert same_value(Decimal(98), "mc", value("98.000 litri"))


def test_other_unit_is_a_miss() -> None:
    assert not same_value(Decimal(98), "mc", value("98 kWh"))


def test_dates_compared_as_iso() -> None:
    assert same_value("2031-03-09", None, value("09/03/2031"))
    assert same_value("2031-03-09", None, value("2031-03-09"))
    assert not same_value("2031-03-09", None, value("03/09/2031"))


def test_codes_ignore_spacing() -> None:
    assert same_value("Q1X 0000000000 Z", None, value("Q1X0000000000Z"))
    assert same_value("5550001111", None, value(Decimal(5550001111)))


def test_passage_contains_quote_whitespace_ignored() -> None:
    passages = [
        Passage(text="Per guasti chiamare\nil numero   verde 800 000000 attivo h24", source=1)
    ]
    assert contains_quote("chiamare il numero verde 800 000000", passages)
    assert not contains_quote("numero verde 800 000001", passages)
