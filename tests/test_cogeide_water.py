from datetime import date
from decimal import Decimal

import pytest

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.detect_parser import UnknownDocument, UnknownLayout, detect_parser
from librarian.ingest.parsers.layouts.cogeide_water import CogeideWater
from librarian.ingest.parsers.parser import Claim, ParseError
from librarian.ingest.parsers.sections import Section

HEADER = "Some S.p.A. cod.fisc/p.IVA 02200370167"
TOTALS = (
    "| Servizi fatturati | |\n|---|---|\n| QUOTA FISSA | 1.000,00 € |\n"
    "| ACQUEDOTTO | 234,56 € |\n| TOTALE FATTURA | 1.234,56 € |"
)
USAGE = "| Consumo del periodo | 12 mc |\n|---|---|\n| Totale consumo fatturato | 12 mc |"


def bill(*texts: str, tables: tuple[str, ...] = (TOTALS, USAGE)) -> list[Element]:
    return [Element(1, "text", t, "body", False) for t in texts] + [
        Element(1, "table", t, "body", False) for t in tables
    ]


def full_bill(totals: str = TOTALS) -> list[Element]:
    return bill(
        HEADER,
        "Bolletta per il servizio idrico integrato",
        "Numero:",
        "Periodo:",
        "111 del 05/02/2030",
        "01/01/2030 - 31/01/2030",
        "Tipo:",
        "Bolletta di prova",
        "Consumi fatturati",
        "Sintesi letture",
        tables=(totals, USAGE),
    )


def test_claims_full_bill() -> None:
    assert CogeideWater().is_this_yours(full_bill()) is Claim.full


def test_provider_without_headings_is_unknown_layout() -> None:
    with pytest.raises(UnknownLayout):
        detect_parser(bill(HEADER))


def test_stranger_is_unknown_document() -> None:
    with pytest.raises(UnknownDocument):
        detect_parser(bill("hello"))


def test_parses_fields() -> None:
    parsed = CogeideWater().parse(full_bill())
    assert parsed.kind == "invoice"
    assert parsed.validity is not None
    assert (parsed.validity.lower, parsed.validity.upper) == (date(2030, 1, 1), date(2030, 1, 31))
    assert parsed.fields == {
        "number": "111",
        "issued_on": date(2030, 2, 5),
        "bill_type": "Bolletta di prova",
        "total_amount": Decimal("1234.56"),
        "consumption_mc": Decimal(12),
        "service": "water",
    }


def test_rejects_lines_that_dont_add_up() -> None:
    wrong = TOTALS.replace("| ACQUEDOTTO | 234,56", "| ACQUEDOTTO | 234,55")
    with pytest.raises(ParseError, match="lines sum to 1234.55, total is 1234.56"):
        CogeideWater().parse(full_bill(wrong))


def test_sections_follow_known_headings() -> None:
    elements = [
        Element(1, "page_header", "Codice utente:", "furniture", False),
        Element(1, "section_header", "Dati intestatario", "body", False),
        Element(1, "section_header", "Mario Rossi", "body", False),
        Element(1, "text", "Via Roma 1", "body", False),
        Element(2, "section_header", "Dati fornitura", "body", False),
        Element(2, "text", "garbage", "body", True),
        Element(2, "text", "Ubicazione: Via Roma 1", "body", False),
    ]
    assert CogeideWater().sections(elements) == [
        Section(
            "Dati intestatario",
            1,
            "Persona a cui è diretta la bolletta\n\nMario Rossi\n\nVia Roma 1",
        ),
        Section("Dati fornitura", 2, "Ubicazione: Via Roma 1"),
    ]


def test_payment_slip_and_after_are_dropped() -> None:
    elements = [
        Element(4, "section_header", "Dati fornitura", "body", False),
        Element(4, "text", "write to us", "body", False),
        Element(7, "section_header", "Bolletta serv. Idrico n. 111 del 05/02/2030", "body", False),
        Element(7, "text", "Codice Avviso 3010", "body", False),
        Element(7, "section_header", "QUANTO E QUANDO PAGARE?", "body", False),
    ]
    assert CogeideWater().sections(elements) == [Section("Dati fornitura", 4, "write to us")]


def test_repeated_heading_is_text() -> None:
    elements = [
        Element(1, "section_header", "COGEIDE S.P.A.", "body", False),
        Element(1, "text", "banner", "body", False),
        Element(2, "section_header", "COGEIDE S.P.A.", "body", False),
        Element(2, "text", "banner", "body", False),
    ]
    assert CogeideWater().sections(elements) == [
        Section("COGEIDE S.P.A.", 1, "banner\n\nCOGEIDE S.P.A.\n\nbanner"),
    ]


def test_known_heading_in_footer_starts_a_section() -> None:
    elements = [
        Element(
            4,
            "section_header",
            "INFORMAZIONI E COMUNICAZIONI PERIODICHE AGLI UTENTI",
            "body",
            False,
        ),
        Element(4, "section_header", "COMUNICAZIONI DELLA COGEIDE", "body", False),
        Element(4, "list_item", "(i) item", "body", False),
        Element(4, "page_footer", "COMUNICAZIONI DELL'AUTORITA'", "furniture", False),
        Element(5, "table", "| a | b |", "body", False),
        Element(5, "page_footer", "Pagina 5", "furniture", False),
    ]
    assert CogeideWater().sections(elements) == [
        Section(
            "INFORMAZIONI E COMUNICAZIONI PERIODICHE AGLI UTENTI",
            4,
            "COMUNICAZIONI DELLA COGEIDE\n\n(i) item",
        ),
        Section("COMUNICAZIONI DELL'AUTORITA'", 4, "| a | b |"),
    ]


def test_table_with_known_heading_starts_a_section() -> None:
    elements = [
        Element(1, "section_header", "Bolletta per il servizio idrico integrato", "body", False),
        Element(1, "text", "Numero:", "body", False),
        Element(1, "table", TOTALS, "body", False),
    ]
    assert CogeideWater().sections(elements) == [
        Section("Bolletta per il servizio idrico integrato", 1, "Numero:"),
        Section("Servizi fatturati", 1, TOTALS),
    ]
