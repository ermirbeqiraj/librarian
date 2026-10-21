import re
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy.dialects.postgresql import Range

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers import sections
from librarian.ingest.parsers.kinds import ElectricityBill
from librarian.ingest.parsers.parser import Claim, Parsed, ParseError, claim
from librarian.ingest.parsers.sections import Section
from librarian.ingest.parsers.values import (
    first_match,
    italian_date,
    italian_decimal,
    italian_month,
    table_rows,
)
from librarian.models.document_kind import DocumentKind

PIVA = "01016870329"
HEADINGS = {"Sintesi degli Importi", "Riepilogo consumi", "Riepilogo letture"}
INVOICE = re.compile(r"Fattura n\. (\S+) del (\S+)")
PERIOD = re.compile(r"Periodo di fatturazione: (.+)")
CONSUMPTION = re.compile(r"Consumi fatturati: (.+)")
TOTAL = re.compile(r"TOTALE DA PAGARE: (.+)")
FIRST_LINE = "Spesa per la materia energia"
BILL_TOTAL = "Totale bolletta"


class DufercoElectricity:
    def is_this_yours(self, elements: list[Element]) -> Claim:
        return claim(elements, PIVA, HEADINGS)

    def parse(self, elements: list[Element]) -> Parsed:
        invoice = first_match(elements, INVOICE, "duferco invoice number")
        first_day, last_day = italian_month(first_match(elements, PERIOD, "duferco period")[1])
        _check_sum(_amounts(elements))
        bill = ElectricityBill(
            number=invoice[1],
            issued_on=italian_date(invoice[2]),
            total_amount=italian_decimal(first_match(elements, TOTAL, "duferco total")[1]),
            consumption_kwh=italian_decimal(
                first_match(elements, CONSUMPTION, "duferco consumption")[1]
            ),
        )
        validity = Range(first_day, last_day, bounds="[]")
        return Parsed(DocumentKind.invoice, validity, asdict(bill))

    def sections(self, elements: list[Element]) -> list[Section]:
        return sections.from_docling(elements)


def _amounts(elements: list[Element]) -> list[list[str]]:
    for e in elements:
        if e.kind == "table":
            rows = table_rows(e.text)
            if rows and rows[0][0] == FIRST_LINE:
                return rows
    raise ParseError("duferco: no Sintesi degli Importi")


def _check_sum(rows: list[list[str]]) -> None:
    lines_sum = Decimal(0)
    for row in rows:
        if row[0] == BILL_TOTAL:
            if lines_sum != italian_decimal(row[1]):
                raise ParseError(f"duferco: lines sum to {lines_sum}, total is {row[1]}")
            return
        lines_sum += italian_decimal(row[1])
    raise ParseError(f"duferco: no {BILL_TOTAL!r}")
