import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from librarian.retrieve.result import Passage, Value

# Each way a unit is written, as (base unit, factor to the base): 167000 litri = 167 mc.
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
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"]


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
    number, got_unit = amount
    # A bare number is taken in the expected unit: 63.33 = 63.33 EUR.
    if unit is None or got_unit is None:
        return number == expected
    if unit.lower() not in UNITS or got_unit.lower() not in UNITS:
        return False
    base, factor = UNITS[unit.lower()]
    got_base, got_factor = UNITS[got_unit.lower()]
    return base == got_base and number * got_factor == expected * factor


def parse_amount(value: Value) -> tuple[Decimal, str | None] | None:
    if isinstance(value.value, Decimal):
        return value.value, value.unit

    match = AMOUNT.fullmatch(value.value.strip())
    if match is None:
        return None
    number = parse_number(match.group(2))
    if number is None:
        return None
    unit = match.group(1) or match.group(3) or value.unit
    return number, unit


def parse_number(text: str) -> Decimal | None:
    """Reads Italian and English writing alike: 1.904,02 and 1,904.02 are both 1904.02."""
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", text):
        # Dots alone with three digits after are thousands: 167.000 litri.
        text = text.replace(".", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def same_text(expected: str, got: Decimal | str) -> bool:
    if isinstance(got, Decimal):
        got = str(got)
    expected_date = parse_date(expected)
    if expected_date is not None:
        return parse_date(got) == expected_date
    return squeeze(expected).casefold() == squeeze(got).casefold()


def parse_date(text: str) -> date | None:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), date_format).date()
        except ValueError:
            pass
    return None


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)
