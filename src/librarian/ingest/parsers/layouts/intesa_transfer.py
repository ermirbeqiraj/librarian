import re
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy.dialects.postgresql import Range

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers import sections
from librarian.ingest.parsers.kinds import BankTransfer
from librarian.ingest.parsers.parser import Claim, Parsed, ParseError
from librarian.ingest.parsers.sections import Section
from librarian.ingest.parsers.values import first_match, italian_date, italian_decimal
from librarian.models.document_kind import DocumentKind

DONE = re.compile(r"Eseguito - Bonifico Istantaneo autorizzato in data .+")
NUMBER = re.compile(r"Numero operazione (\S+)")
BENEFICIARY = re.compile(r"Beneficiario (.+)")
EXECUTED = re.compile(r"Data addebito ordinante (\S+)")
AMOUNT = re.compile(r"Importo (.+) Euro")
FEE = re.compile(r"Commissioni (.+) Euro Totale operazione")
TOTAL = re.compile(r"(.+) Euro")


class IntesaTransfer:
    def is_this_yours(self, elements: list[Element]) -> Claim:
        if any(DONE.fullmatch(e.text) for e in elements):
            return Claim.full
        return Claim.no

    def parse(self, elements: list[Element]) -> Parsed:
        executed_on = italian_date(first_match(elements, EXECUTED, "transfer date")[1])
        transfer = BankTransfer(
            number=first_match(elements, NUMBER, "transfer number")[1],
            executed_on=executed_on,
            beneficiary=first_match(elements, BENEFICIARY, "beneficiary")[1],
            amount=italian_decimal(first_match(elements, AMOUNT, "transfer amount")[1]),
            fee=italian_decimal(first_match(elements, FEE, "transfer fee")[1]),
            total_amount=_total(elements),
        )
        if transfer.amount + transfer.fee != transfer.total_amount:
            raise ParseError(
                f"transfer: {transfer.amount} + {transfer.fee} is not {transfer.total_amount}"
            )
        validity = Range(executed_on, executed_on, bounds="[]")
        return Parsed(DocumentKind.receipt, validity, asdict(transfer))

    def sections(self, elements: list[Element]) -> list[Section]:
        return sections.from_docling(elements)


def _total(elements: list[Element]) -> Decimal:
    for i in range(len(elements) - 1):
        if FEE.fullmatch(elements[i].text):
            total = TOTAL.fullmatch(elements[i + 1].text)
            if total:
                return italian_decimal(total[1])
    raise ParseError("transfer: no total")
