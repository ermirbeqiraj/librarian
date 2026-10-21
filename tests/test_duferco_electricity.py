from datetime import date
from decimal import Decimal

import pytest

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.layouts.duferco_electricity import DufercoElectricity
from librarian.ingest.parsers.parser import Claim, ParseError

AMOUNTS = (
    "| Spesa per la materia energia | 10,00 euro |\n|---|---|\n"
    "| IVA | 1,00 euro |\n| Totale bolletta | 11,00 euro |\n"
    "| Canone di abbonamento alla televisione per uso privato | 9,00 euro |"
)


def bill(amounts: str = AMOUNTS) -> list[Element]:
    texts = [
        ("section_header", "Fattura n. 111FT del 05/02/2030"),
        ("text", "Periodo di fatturazione: Gennaio 2030"),
        ("text", "Consumi fatturati: 50 kWh"),
        ("text", "TOTALE DA PAGARE: 20,00 euro"),
        ("section_header", "Sintesi degli Importi"),
        ("table", amounts),
        ("section_header", "Riepilogo consumi"),
        ("section_header", "Riepilogo letture"),
        ("text", "P.IVA: 01016870329"),
    ]
    return [Element(1, kind, text, "body", False) for kind, text in texts]


def test_claims_full_bill() -> None:
    assert DufercoElectricity().is_this_yours(bill()) is Claim.full


def test_parses_fields() -> None:
    parsed = DufercoElectricity().parse(bill())
    assert parsed.kind == "invoice"
    assert parsed.validity is not None
    assert (parsed.validity.lower, parsed.validity.upper) == (date(2030, 1, 1), date(2030, 1, 31))
    assert parsed.fields == {
        "number": "111FT",
        "issued_on": date(2030, 2, 5),
        "total_amount": Decimal("20.00"),
        "consumption_kwh": Decimal(50),
        "service": "electricity",
    }


def test_rejects_lines_that_dont_add_up() -> None:
    with pytest.raises(ParseError, match="lines sum to 10.99"):
        DufercoElectricity().parse(bill(AMOUNTS.replace("| 1,00 euro", "| 0,99 euro")))
