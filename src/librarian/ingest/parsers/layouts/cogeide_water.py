import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise, takewhile

from sqlalchemy.dialects.postgresql import Range

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers import sections
from librarian.ingest.parsers.parser import Claim, Parsed, ParseError
from librarian.ingest.parsers.sections import Section
from librarian.ingest.parsers.values import italian_date, italian_decimal, table_rows
from librarian.models.document_kind import DocumentKind

PIVA = "02200370167"
HEADINGS = {"Bolletta per il servizio idrico integrato", "Consumi fatturati", "Sintesi letture"}
NUMBER = re.compile(r"(\d+) del (\d{2}/\d{2}/\d{4})")
PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4}) - (\d{2}/\d{2}/\d{4})")
TOTAL = "TOTALE FATTURA"
PAYMENT_SLIP = "Bolletta serv. Idrico n."
HEADING_KINDS = {"section_header", "page_footer"}

EXTRA_HEADING = {"Dati intestatario": "Persona a cui è diretta la bolletta"}

SECTION_HEADINGS = (
    "COGEIDE S.P.A.",
    "Dati intestatario",
    "Dati fornitura",
    "Servizio clienti",
    "Contatti utili e reclami",
    "Pronto Intervento",
    "Letture e autoletture",
    "Comunicazioni",
    "Bolletta per il servizio idrico integrato",
    "Servizi fatturati",
    "Consumi fatturati",
    "Sintesi letture",
    "Dati delle letture",
    "Dettaglio della sua bolletta",
    "INFORMAZIONI E COMUNICAZIONI PERIODICHE AGLI UTENTI",
    "COMUNICAZIONI DELL'AUTORITA'",
    PAYMENT_SLIP,
)


@dataclass(frozen=True)
class WaterBill:
    number: str
    issued_on: date
    bill_type: str
    total_amount: Decimal
    consumption_mc: Decimal
    service: str = "water"


class CogeideWater:
    def is_this_yours(self, elements: list[Element]) -> Claim:
        if not any(PIVA in e.text for e in elements):
            return Claim.no
        if HEADINGS <= {e.text for e in elements}:
            return Claim.full
        return Claim.provider

    def parse(self, elements: list[Element]) -> Parsed:
        number = _match(elements, NUMBER, "number")
        period = _match(elements, PERIOD, "period")
        bill = WaterBill(
            number=number[1],
            issued_on=italian_date(number[2]),
            bill_type=_after(elements, "Tipo:"),
            total_amount=italian_decimal(_cell(elements, TOTAL)),
            consumption_mc=italian_decimal(_cell(elements, "Consumo del periodo")),
        )
        _check_sum(elements, bill.total_amount)
        validity = Range(italian_date(period[1]), italian_date(period[2]), bounds="[]")
        return Parsed(DocumentKind.invoice, validity, asdict(bill))

    def sections(self, elements: list[Element]) -> list[Section]:
        body = [e for e in elements if (e.layer == "body" or _is_heading(e)) and not e.in_picture]
        found = sections.split(list(_with_table_headings(body)), _is_heading)
        kept = list(takewhile(lambda s: not s.heading.startswith(PAYMENT_SLIP), found))
        result: list[Section] = []
        for s in kept:
            if s.heading in EXTRA_HEADING:
                s = Section(s.heading, s.page, EXTRA_HEADING[s.heading] + "\n\n" + s.text)
            result.append(s)
        return result


def _with_table_headings(elements: list[Element]) -> Iterator[Element]:
    for e in elements:
        rows = table_rows(e.text) if e.kind == "table" else []
        if rows and rows[0][0].startswith(SECTION_HEADINGS):
            yield Element(e.page, "section_header", rows[0][0], e.layer, False)
        yield e


def _is_heading(element: Element) -> bool:
    return element.kind in HEADING_KINDS and element.text.startswith(SECTION_HEADINGS)


def _check_sum(elements: list[Element], total: Decimal) -> None:
    lines = takewhile(lambda row: row[0] != TOTAL, _table(elements, "Servizi fatturati")[1:])
    lines_sum = sum((italian_decimal(row[1]) for row in lines), Decimal(0))
    if lines_sum != total:
        raise ParseError(f"water bill: lines sum to {lines_sum}, total is {total}")


def _match(elements: list[Element], pattern: re.Pattern[str], name: str) -> re.Match[str]:
    for e in elements:
        if match := pattern.fullmatch(e.text):
            return match
    raise ParseError(f"water bill: no {name}")


def _after(elements: list[Element], label: str) -> str:
    for current, following in pairwise(elements):
        if current.text == label:
            return following.text
    raise ParseError(f"water bill: nothing after {label!r}")


def _table(elements: list[Element], first_cell: str) -> list[list[str]]:
    for e in elements:
        if e.kind == "table":
            rows = table_rows(e.text)
            if rows and rows[0][0] == first_cell:
                return rows
    raise ParseError(f"water bill: no table {first_cell!r}")


def _cell(elements: list[Element], label: str) -> str:
    for e in elements:
        if e.kind == "table":
            for row in table_rows(e.text):
                if row[0] == label:
                    return row[1]
    raise ParseError(f"water bill: no row {label!r}")
