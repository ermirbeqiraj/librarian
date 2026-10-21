import calendar
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.parser import ParseError

MONTHS = [
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
]


def italian_date(text: str) -> date:
    try:
        return datetime.strptime(text.replace(".", "/"), "%d/%m/%Y").date()
    except ValueError as error:
        raise ParseError(f"not a date: {text!r}") from error


def italian_month(text: str) -> tuple[date, date]:
    words = text.lower().split()
    if len(words) != 2 or words[0] not in MONTHS or not words[1].isdigit():
        raise ParseError(f"not a month: {text!r}")
    month = MONTHS.index(words[0]) + 1
    year = int(words[1])
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def italian_decimal(text: str) -> Decimal:
    digits = re.sub(r"[^\d,.-]", "", text)
    try:
        return Decimal(digits.replace(".", "").replace(",", "."))
    except InvalidOperation as error:
        raise ParseError(f"not a number: {text!r}") from error


def table_rows(markdown: str) -> list[list[str]]:
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in markdown.splitlines()
        if not set(line.strip()) <= set("|-: ")
    ]


def first_match(elements: list[Element], pattern: re.Pattern[str], what: str) -> re.Match[str]:
    for e in elements:
        if match := pattern.fullmatch(e.text):
            return match
    raise ParseError(f"no {what}")
