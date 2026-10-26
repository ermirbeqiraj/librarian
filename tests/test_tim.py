from datetime import date
from decimal import Decimal

import pytest

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.layouts.tim import Tim
from librarian.ingest.parsers.parser import Claim, ParseError

COSTS = (
    "| Offerta TIM | Periodo | IVA incl. |\n|---|---|---|\n"
    "| WiFi Casa | giu 30 | 20,00 |\n| Sconto | giu 30 | -5,00 |\n"
    "| | Offerta TIM Totale 15,00 | Offerta TIM Totale 15,00 |\n"
    "| Altri importi | Periodo | IVA incl. |\n| Rata | | 5,00 |\n"
    "| | Totale da pagare | € 20,00 |"
)
NO_TOTAL = COSTS.replace("Totale da pagare", "Totale")


def bill(costs: str = COSTS) -> list[Element]:
    texts = [
        ("section_header", "Informazioni cliente"),
        ("text", "P. IVA e n. di Iscrizione al Registro delle Imprese: 00488410010"),
        ("section_header", "Fattura Giugno 2030"),
        ("text", "Numero fattura: RB111"),
        ("text", "Data emissione: 16/06/2030"),
        ("section_header", "Dettaglio dei costi"),
        ("table", costs),
        ("section_header", "AVVISO DI PAGAMENTO"),
    ]
    return [Element(1, kind, text, "body", False) for kind, text in texts]


def test_claims_full_bill() -> None:
    assert Tim().is_this_yours(bill()) is Claim.full


def test_parses_fields() -> None:
    parsed = Tim().parse(bill())
    assert parsed.kind == "invoice"
    assert parsed.validity is not None
    assert (parsed.validity.lower, parsed.validity.upper) == (date(2030, 6, 1), date(2030, 6, 30))
    assert parsed.fields == {
        "number": "RB111",
        "issued_on": date(2030, 6, 16),
        "total_amount": Decimal("20.00"),
        "service": "phone",
    }


def test_takes_total_even_when_lines_dont_add_up() -> None:
    parsed = Tim().parse(bill(COSTS.replace("| -5,00 |", "| -5,00 Totale -5,00 |")))
    assert parsed.fields["total_amount"] == Decimal("20.00")


def test_total_under_its_label_when_the_table_has_none() -> None:
    elements = bill(NO_TOTAL) + [
        Element(2, "section_header", "Totale da pagare", "body", False),
        Element(2, "text", "€ 1.234,50", "body", False),
    ]
    assert Tim().parse(elements).fields["total_amount"] == Decimal("1234.50")


def test_total_after_the_issue_date_when_nothing_else_has_it() -> None:
    elements = bill(NO_TOTAL)
    elements.insert(5, Element(1, "text", "€ 20,00", "body", False))
    assert Tim().parse(elements).fields["total_amount"] == Decimal("20.00")


def test_rejects_bill_without_total() -> None:
    with pytest.raises(ParseError, match="no 'Totale da pagare'"):
        Tim().parse(bill(NO_TOTAL))
