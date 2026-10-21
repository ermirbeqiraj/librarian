from datetime import date
from decimal import Decimal

import pytest

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.detect_parser import UnknownLayout, detect_parser
from librarian.ingest.parsers.layouts.hera import Hera
from librarian.ingest.parsers.parser import Claim, ParseError
from librarian.ingest.parsers.sections import Section

HEADER = "Gruppo IVA P.IVA 03819031208"
RECEIPT = (
    "| Quantità | Importi | Prezzo medio |\n|---|---|---|\n"
    "| Quota per consumi | | |\n| 10 Smc | 100,00 € | 10 €/Smc |\n"
    "| di cui spesa per la vendita | 60,00 € | 6 €/Smc |\n"
    "| Accise e IVA ....... | 20,00 € | |\n| Totale bolletta | 120,00 € | |\n"
    "| Prodotti e/o servizi aggiuntivi | 5,00 € | |\n| Totale da pagare | 125,00 € | |"
)


def text(page: int, value: str, kind: str = "text") -> Element:
    return Element(page, kind, value, "body", False)


def heading(page: int, value: str) -> Element:
    return text(page, value, "section_header")


def full_bill(receipt: str = RECEIPT) -> list[Element]:
    return [
        text(1, HEADER),
        heading(1, "Informazioni bolletta"),
        text(1, "Servizio fatturato:"),
        text(1, "Gas"),
        text(1, "Data emissione:"),
        text(1, "05.02.2030"),
        text(1, "Numero fattura elettronica valida ai fini fiscali:"),
        text(1, "111"),
        text(1, "Periodo oggetto di fatturazione:"),
        text(1, "dal 01.01.2030 al 31.01.2030"),
        text(1, "Consumo totale fatturato del periodo:"),
        text(1, "10,000000 Smc"),
        heading(2, "Scontrino dell'energia"),
        text(2, receipt, "table"),
        heading(2, "Box dell'offerta"),
    ]


def test_claims_full_bill() -> None:
    assert Hera().is_this_yours(full_bill()) is Claim.full


def test_unknown_hera_layout() -> None:
    with pytest.raises(UnknownLayout):
        detect_parser([text(1, HEADER), heading(1, "Riepilogo letture")])


def test_parses_fields() -> None:
    parsed = Hera().parse(full_bill())
    assert parsed.kind == "invoice"
    assert parsed.validity is not None
    assert (parsed.validity.lower, parsed.validity.upper) == (date(2030, 1, 1), date(2030, 1, 31))
    assert parsed.fields == {
        "number": "111",
        "issued_on": date(2030, 2, 5),
        "total_amount": Decimal("125.00"),
        "consumption_smc": Decimal(10),
        "service": "gas",
    }


def test_rejects_lines_that_dont_add_up() -> None:
    wrong = RECEIPT.replace("| 20,00 €", "| 19,99 €")
    with pytest.raises(ParseError, match="lines sum to 119.99, Totale bolletta is 120.00"):
        Hera().parse(full_bill(wrong))


def test_electricity_counts_kwh() -> None:
    elements = full_bill()
    elements[3] = heading(1, "Energia elettrica")
    elements[11] = text(1, "10,000000 kWh")
    parsed = Hera().parse(elements)
    assert parsed.kind == "invoice"
    assert parsed.fields["service"] == "electricity"
    assert parsed.fields["consumption_kwh"] == Decimal(10)


def test_rejects_other_services() -> None:
    elements = full_bill()
    elements[3] = text(1, "Acqua")
    with pytest.raises(ParseError, match="not handled"):
        Hera().parse(elements)


def test_pages_before_the_cover_are_one_notes_section() -> None:
    elements = [
        heading(1, "Oggetto: a letter"),
        text(1, "Cordiali saluti FirstPageCheck MARIO ROSSI"),
        text(3, "Gentile Cliente, another note"),
        text(5, "Gentile MARIO ROSSI, le inviamo il riepilogo"),
        heading(6, "Contatti"),
        text(6, "Call us"),
    ]
    assert Hera().sections(elements) == [
        Section(
            "Comunicazioni",
            1,
            "Oggetto: a letter\n\nCordiali saluti\n\nGentile Cliente, another note",
        ),
        Section("Riepilogo", 5, "Gentile MARIO ROSSI, le inviamo il riepilogo"),
        Section("Contatti", 6, "Call us"),
    ]


def test_without_notes_the_cover_comes_first() -> None:
    elements = [text(1, "le inviamo il riepilogo"), heading(2, "Contatti")]
    assert [s.heading for s in Hera().sections(elements)] == ["Riepilogo", "Contatti"]


def test_cleaning() -> None:
    elements = [
        text(1, "le inviamo il riepilogo"),
        Element(1, "page_header", "pag. 1", "furniture", False),
        Element(1, "text", "jcbZ8XRwRJoz:jcbZ", "body", True),
        text(1, "vppXlvzhHL4PHtX"),
        Element(1, "text", "Totale spesa annua: 1.000,00 €", "body", True),
        text(1, "€/Smc"),
        heading(2, "Elementi informativi essenziali"),
        heading(2, "Imposte"),
        text(2, "| a | a | 1 |\n|---|---|---|\n| | | |", "table"),
        heading(3, "Imposte (segue)"),
        text(3, "more"),
    ]
    assert Hera().sections(elements) == [
        Section(
            "Riepilogo", 1, "le inviamo il riepilogo\n\nTotale spesa annua: 1.000,00 €\n\n€/Smc"
        ),
        Section("Imposte", 2, "| a | 1 |\n\nImposte (segue)\n\nmore"),
    ]
