import re
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy.dialects.postgresql import Range

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers import sections
from librarian.ingest.parsers.kinds import PhoneBill
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

PIVA = "00488410010"
HEADINGS = {"Informazioni cliente", "Dettaglio dei costi", "AVVISO DI PAGAMENTO"}
NUMBER = re.compile(r"Numero fattura: (\S+)")
ISSUED = re.compile(r"Data emissione: (\S+)")
MONTH = re.compile(r"Fattura (\S+ \d{4})")
TOTAL = "Totale da pagare"


class Tim:
    def is_this_yours(self, elements: list[Element]) -> Claim:
        return claim(elements, PIVA, HEADINGS)

    def parse(self, elements: list[Element]) -> Parsed:
        first_day, last_day = italian_month(first_match(elements, MONTH, "tim month")[1])
        bill = PhoneBill(
            number=first_match(elements, NUMBER, "tim number")[1],
            issued_on=italian_date(first_match(elements, ISSUED, "tim issue date")[1]),
            total_amount=_total(_costs(elements)),
        )
        validity = Range(first_day, last_day, bounds="[]")
        return Parsed(DocumentKind.invoice, validity, asdict(bill))

    def sections(self, elements: list[Element]) -> list[Section]:
        return sections.from_docling(elements)


def _costs(elements: list[Element]) -> list[list[str]]:
    for e in elements:
        if e.kind == "table" and TOTAL in e.text:
            return table_rows(e.text)
    raise ParseError("tim: no Dettaglio dei costi")


def _total(rows: list[list[str]]) -> Decimal:
    for row in rows:
        if TOTAL in row:
            return italian_decimal(row[-1])
    raise ParseError(f"tim: no {TOTAL!r}")
