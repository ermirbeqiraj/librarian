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


def test_rejects_lines_that_dont_add_up() -> None:
    with pytest.raises(ParseError, match="lines sum to 19.99, total is 20.00"):
        Tim().parse(bill(COSTS.replace("| -5,00 |", "| -5,01 |")))
