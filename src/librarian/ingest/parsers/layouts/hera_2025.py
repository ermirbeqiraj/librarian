import re
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy.dialects.postgresql import Range

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers import sections
from librarian.ingest.parsers.kinds import GasBill
from librarian.ingest.parsers.layouts.hera_common import (
    NOTES,
    PIVA,
    SUMMARY,
    after,
    amount,
    clean,
    heading,
    label,
    table,
    with_notes_and_cover,
)
from librarian.ingest.parsers.parser import Claim, Parsed, ParseError, claim
from librarian.ingest.parsers.sections import Section
from librarian.ingest.parsers.values import first_match, italian_date, italian_decimal, table_rows
from librarian.models.document_kind import DocumentKind

HEADINGS = {
    "Informazioni contrattuali",
    "Informazioni tecniche",
    "Storico consumi medi giornalieri Smc",
}
NUMBER = re.compile(r"Numero fattura elettronica valida ai fini fiscali (\d+)")
ISSUED = re.compile(r"Data emissione (\S+)")
PERIOD = re.compile(r"Periodo: dal (\S+) al (\S+)")
TOTAL = re.compile(r"Totale fattura (.+)")
COVER = "Servizi intestati a"
AMOUNTS = "Sintesi importi fatturati"
AMOUNTS_TOTAL = "Totale bolletta/contratto"

RENAMED = {"ESTENERGY S.p.A.": "Informazioni bolletta"}
TABLE_HEADINGS = {AMOUNTS, "Informazioni materia gas naturale"}
SECTION_HEADINGS = {
    NOTES,
    SUMMARY,
    "Contatti",
    "Consumo stimato e Autolettura",
    "Modalità di pagamento",
    "Comunicazioni e reclami scritti",
    "Informazioni bolletta",
    "Informazioni contrattuali",
    "Informazioni tecniche",
    "Sintesi consumi fatturati",
    "Storico consumi medi giornalieri Smc",
    "Riepilogo letture",
    "Imposte e IVA",
    "Altri servizi",
    "Informazioni contratto",
    "Società emittente",
    "TRATTAMENTO DEI DATI PERSONALI",
    "Accertamenti della sicurezza post contatore: Delibera 40/2014/R/gas",
    "Risoluzione extragiudiziale delle controversie",
} | TABLE_HEADINGS


class Hera2025:
    def is_this_yours(self, elements: list[Element]) -> Claim:
        return claim(elements, PIVA, HEADINGS)

    def parse(self, elements: list[Element]) -> Parsed:
        period = first_match(elements, PERIOD, "hera 2025 period")
        validity = Range(italian_date(period[1]), italian_date(period[2]), bounds="[]")
        _check_sum(table(elements, AMOUNTS))
        bill = GasBill(
            number=first_match(elements, NUMBER, "hera 2025 number")[1],
            issued_on=italian_date(first_match(elements, ISSUED, "hera 2025 issue date")[1]),
            total_amount=italian_decimal(first_match(elements, TOTAL, "hera 2025 total")[1]),
            consumption_smc=italian_decimal(
                after(elements, "Consumo fatturato (Standard metri cubi)")
            ),
        )
        return Parsed(DocumentKind.invoice, validity, asdict(bill))

    def sections(self, elements: list[Element]) -> list[Section]:
        kept = with_notes_and_cover(_renamed(_with_table_headings(clean(elements))), COVER)
        return sections.split(kept, _is_heading)


def _with_table_headings(elements: list[Element]) -> list[Element]:
    result: list[Element] = []
    for e in elements:
        if e.kind == "table":
            rows = table_rows(e.text)
            if rows and rows[0][0] in TABLE_HEADINGS:
                result.append(heading(rows[0][0], e.page))
        result.append(e)
    return result


def _renamed(elements: list[Element]) -> list[Element]:
    result: list[Element] = []
    for e in elements:
        if e.kind == "section_header" and e.text in RENAMED:
            e = heading(RENAMED[e.text], e.page)
        result.append(e)
    return result


def _is_heading(element: Element) -> bool:
    return element.kind == "section_header" and element.text in SECTION_HEADINGS


def _check_sum(rows: list[list[str]]) -> None:
    total = amount(rows, AMOUNTS_TOTAL, column=1)
    lines_sum = Decimal(0)
    for row in rows[1:]:
        if label(row[1]) == AMOUNTS_TOTAL:
            break
        lines_sum += italian_decimal(row[2])
    if lines_sum != total:
        raise ParseError(f"hera 2025: lines sum to {lines_sum}, total is {total}")
