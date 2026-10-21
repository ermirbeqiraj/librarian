import re
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy.dialects.postgresql import Range

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers import sections
from librarian.ingest.parsers.kinds import ElectricityBill, GasBill
from librarian.ingest.parsers.layouts.hera_common import (
    NOTES,
    PIVA,
    SUMMARY,
    after,
    amount,
    clean,
    label,
    table,
    with_notes_and_cover,
)
from librarian.ingest.parsers.parser import Claim, Parsed, ParseError, claim
from librarian.ingest.parsers.sections import Section
from librarian.ingest.parsers.values import italian_date, italian_decimal
from librarian.models.document_kind import DocumentKind

HEADINGS = {"Informazioni bolletta", "Scontrino dell'energia", "Box dell'offerta"}
PERIOD = re.compile(r"dal (\S+) al (\S+)")
COVER = "le inviamo il riepilogo"
CHAPTER = "Elementi informativi essenziali"

SECTION_HEADINGS = {
    NOTES,
    SUMMARY,
    "Contatti",
    "Modalità di pagamento",
    "Comunicazioni e reclami scritti",
    "Informazioni bolletta",
    "Pagamenti e consumi",
    "Servizio Clienti 800 046 200",
    "Scontrino dell'energia",
    "Box dell'offerta",
    "Informazioni storiche",
    "Caratteristiche tecniche della fornitura",
    "Letture e consumi",
    "Informazioni relative a pagamenti e rateizzazioni",
    "Imposte",
    "Informazioni per il consumatore",
    "Mix energetico e altre informazioni",
    "Oneri generali di sistema",
    "Come trovare gli altri strumenti di trasparenza",
    "Comunicazioni dell'Autorità di Regolazione per Energia Reti e Ambiente",
    "Ulteriori obblighi informativi",
    "Altre comunicazioni",
}


class Hera:
    def is_this_yours(self, elements: list[Element]) -> Claim:
        return claim(elements, PIVA, HEADINGS)

    def parse(self, elements: list[Element]) -> Parsed:
        period = PERIOD.fullmatch(after(elements, "Periodo oggetto di fatturazione:"))
        if period is None:
            raise ParseError("hera: no period")
        validity = Range(italian_date(period[1]), italian_date(period[2]), bounds="[]")
        receipt = table(elements, "Quantità")
        _check_sum(receipt)

        number = after(elements, "Numero fattura elettronica valida ai fini fiscali:")
        issued_on = italian_date(after(elements, "Data emissione:"))
        total = amount(receipt, "Totale da pagare")
        consumption = italian_decimal(after(elements, "Consumo totale fatturato del periodo:"))

        service = after(elements, "Servizio fatturato:")
        if service == "Gas":
            bill = GasBill(number, issued_on, total, consumption)
            return Parsed(DocumentKind.invoice, validity, asdict(bill))
        if service == "Energia elettrica":
            bill = ElectricityBill(number, issued_on, total, consumption)
            return Parsed(DocumentKind.invoice, validity, asdict(bill))
        raise ParseError(f"hera: service {service!r} not handled")

    def sections(self, elements: list[Element]) -> list[Section]:
        kept = [e for e in clean(elements) if e.text != CHAPTER]
        return sections.split(with_notes_and_cover(kept, COVER), _is_heading)


def _is_heading(element: Element) -> bool:
    return element.kind == "section_header" and element.text in SECTION_HEADINGS


def _check_sum(receipt: list[list[str]]) -> None:
    bill_total = amount(receipt, "Totale bolletta")
    lines_sum = Decimal(0)
    for row in receipt[1:]:
        row_label = label(row[0])
        if row_label == "Totale bolletta":
            break
        if row[1] != "" and not row_label.startswith("di cui"):
            lines_sum += italian_decimal(row[1])
    if lines_sum != bill_total:
        raise ParseError(f"hera: lines sum to {lines_sum}, Totale bolletta is {bill_total}")
