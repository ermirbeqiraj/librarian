from datetime import date
from decimal import Decimal

import pytest

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.layouts.hera_2025 import Hera2025
from librarian.ingest.parsers.parser import Claim, ParseError
from librarian.ingest.parsers.sections import Section

HEADER = "Gruppo IVA P.IVA 03819031208"
AMOUNTS = (
    "| Sintesi importi fatturati | | |\n|---|---|---|\n"
    "| | Spesa per la materia gas naturale ..... | 10,00 € |\n"
    "| | Spesa per oneri di sistema ..... | -1,00 € |\n"
    "| | Totale bolletta/contratto | 9,00 € |"
)


def text(page: int, value: str, kind: str = "text") -> Element:
    return Element(page, kind, value, "body", False)


def heading(page: int, value: str) -> Element:
    return text(page, value, "section_header")


def full_bill(amounts: str = AMOUNTS) -> list[Element]:
    return [
        text(1, HEADER),
        heading(1, "Numero fattura elettronica valida ai fini fiscali 111"),
        text(1, "Data emissione 05.02.2030"),
        text(1, "Periodo: dal 01.01.2030 al 31.01.2030"),
        heading(1, "Informazioni contrattuali"),
        heading(1, "Informazioni tecniche"),
        text(1, amounts, "table"),
        text(1, "Consumo fatturato (Standard metri cubi)"),
        text(1, "10,000000 Smc"),
        heading(1, "Storico consumi medi giornalieri Smc"),
        heading(2, "Totale fattura 30,00 €"),
    ]


def test_claims_full_bill() -> None:
    assert Hera2025().is_this_yours(full_bill()) is Claim.full


def test_parses_fields() -> None:
    parsed = Hera2025().parse(full_bill())
    assert parsed.kind == "invoice"
    assert parsed.validity is not None
    assert (parsed.validity.lower, parsed.validity.upper) == (date(2030, 1, 1), date(2030, 1, 31))
    assert parsed.fields == {
        "number": "111",
        "issued_on": date(2030, 2, 5),
        "total_amount": Decimal("30.00"),
        "consumption_smc": Decimal(10),
        "service": "gas",
    }


def test_rejects_lines_that_dont_add_up() -> None:
    wrong = AMOUNTS.replace("| -1,00 €", "| -1,01 €")
    with pytest.raises(ParseError, match="lines sum to 8.99, total is 9.00"):
        Hera2025().parse(full_bill(wrong))


def test_sections() -> None:
    elements = [
        text(1, "an ad"),
        heading(3, "Servizi intestati a MARIO ROSSI"),
        heading(5, "ESTENERGY S.p.A."),
        text(5, "Data emissione 05.02.2030"),
        text(5, "| Sintesi importi fatturati | |\n|---|---|\n| | 9,00 € |", "table"),
    ]
    assert Hera2025().sections(elements) == [
        Section("Comunicazioni", 1, "an ad"),
        Section("Riepilogo", 3, "Servizi intestati a MARIO ROSSI"),
        Section("Informazioni bolletta", 5, "Data emissione 05.02.2030"),
        Section("Sintesi importi fatturati", 5, "| Sintesi importi fatturati |  |\n|  | 9,00 € |"),
    ]
