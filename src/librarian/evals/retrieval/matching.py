import re
from datetime import date
from decimal import Decimal, InvalidOperation

from librarian.retrieve.result import Passage, Value

# Each way a unit is written, as (base unit, factor to the base): 152000 litri = 152 mc.
UNITS = {
    "€": ("EUR", Decimal(1)),
    "eur": ("EUR", Decimal(1)),
    "euro": ("EUR", Decimal(1)),
    "mc": ("mc", Decimal(1)),
    "m3": ("mc", Decimal(1)),
    "m³": ("mc", Decimal(1)),
    "l": ("mc", Decimal("0.001")),
    "lt": ("mc", Decimal("0.001")),
    "litri": ("mc", Decimal("0.001")),
    "litro": ("mc", Decimal("0.001")),
    "smc": ("Smc", Decimal(1)),
    "kwh": ("kWh", Decimal(1)),
}
AMOUNT = re.compile(r"(€)?\s*(-?[\d.,]+)\s*(\S*)")


def contains_quote(quote: str, passages: list[Passage]) -> bool:
    wanted = squeeze(quote)
    for passage in passages:
        if wanted in squeeze(passage.text):
            return True
    return False


def any_same_value(expected: Decimal | str, unit: str | None, values: list[Value]) -> bool:
    for value in values:
        if same_value(expected, unit, value):
            return True
    return False


def same_value(expected: Decimal | str, unit: str | None, got: Value) -> bool:
    if isinstance(expected, str):
        return same_text(expected, got.value)

    amount = parse_amount(got)
    if amount is None:
        return False
    numbers, got_unit = amount
    for number in numbers:
        if same_amount(expected, unit, number, got_unit):
            return True
    return False


def same_amount(expected: Decimal, unit: str | None, number: Decimal, got_unit: str | None) -> bool:
    # A bare number is taken in the expected unit: 63.33 = 63.33 EUR.
    if unit is None or got_unit is None:
        return number == expected
    if unit.lower() not in UNITS or got_unit.lower() not in UNITS:
        return False
    base, factor = UNITS[unit.lower()]
    got_base, got_factor = UNITS[got_unit.lower()]
    return base == got_base and number * got_factor == expected * factor


def parse_amount(value: Value) -> tuple[list[Decimal], str | None] | None:
    if isinstance(value.value, Decimal):
        return [value.value], value.unit

    match = AMOUNT.fullmatch(value.value.strip())
    if match is None:
        return None
    numbers = parse_numbers(match.group(2))
    if not numbers:
        return None
    unit = match.group(1) or match.group(3) or value.unit
    return numbers, unit


def parse_numbers(text: str) -> list[Decimal]:
    """Every way the number can be read. Italian and English writing alike: 1.876,35 and
    1,876.35 are both 1876.35. One dot with three digits after can be either: 318.746 kWh is
    a decimal, 152.000 litri is thousands, so both readings come back."""
    readings: list[str] = []
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            readings.append(text.replace(".", "").replace(",", "."))
        else:
            readings.append(text.replace(",", ""))
    elif "," in text:
        readings.append(text.replace(",", "."))
    elif text.count(".") > 1:
        readings.append(text.replace(".", ""))
    elif re.fullmatch(r"-?\d{1,3}\.\d{3}", text):
        readings.append(text.replace(".", ""))
        readings.append(text)
    else:
        readings.append(text)
    numbers: list[Decimal] = []
    for reading in readings:
        try:
            numbers.append(Decimal(reading))
        except InvalidOperation:
            pass
    return numbers


def same_text(expected: str, got: Decimal | str) -> bool:
    if isinstance(got, Decimal):
        got = str(got)
    expected_date = parse_date(expected)
    if expected_date is not None:
        return parse_date(got) == expected_date
    return squeeze(expected).casefold() == squeeze(got).casefold()


def parse_date(text: str) -> date | None:
    """Dates are ISO, by rule (the dig instructions): any other writing is a miss, the model
    didn't follow it."""
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)
