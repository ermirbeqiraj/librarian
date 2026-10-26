import re
from dataclasses import asdict
from decimal import Decimal
from itertools import pairwise

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
TOTAL_LABEL = re.compile(TOTAL)
AMOUNT = re.compile(r"€ -?[\d.]+,\d{2}")


class Tim:
    def is_this_yours(self, elements: list[Element]) -> Claim:
        return claim(elements, PIVA, HEADINGS)

    def parse(self, elements: list[Element]) -> Parsed:
        first_day, last_day = italian_month(first_match(elements, MONTH, "tim month")[1])
        bill = PhoneBill(
            number=first_match(elements, NUMBER, "tim number")[1],
            issued_on=italian_date(first_match(elements, ISSUED, "tim issue date")[1]),
            total_amount=_total(elements),
        )
        validity = Range(first_day, last_day, bounds="[]")
        return Parsed(DocumentKind.invoice, validity, asdict(bill))

    def sections(self, elements: list[Element]) -> list[Section]:
        return sections.from_docling(elements)


def _total(elements: list[Element]) -> Decimal:
    """From the cost table, else the amount under 'Totale da pagare', else the one after the
    issue date: the portal's copy of a bill doesn't always keep the total in the table."""
    for e in elements:
        if e.kind == "table" and TOTAL in e.text:
            for row in table_rows(e.text):
                if TOTAL in row:
                    return italian_decimal(row[-1])
    for label in (TOTAL_LABEL, ISSUED):
        if amount := _amount_after(elements, label):
            return italian_decimal(amount)
    raise ParseError(f"tim: no {TOTAL!r}")


def _amount_after(elements: list[Element], label: re.Pattern[str]) -> str | None:
    for before, e in pairwise(elements):
        if label.fullmatch(before.text) and AMOUNT.fullmatch(e.text):
            return e.text
    return None
