from datetime import date
from decimal import Decimal

import pytest

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.layouts.intesa_transfer import IntesaTransfer
from librarian.ingest.parsers.parser import Claim, ParseError


def transfer(total: str = "11,00 Euro") -> list[Element]:
    texts = [
        "Eseguito - Bonifico Istantaneo autorizzato in data 08.10.2030 14:36",
        "Numero operazione INTER111",
        "Beneficiario SCUOLA DI MUSICA",
        "Beneficiario effettivo",
        "Data addebito ordinante 08.10.2030",
        "Importo 10,00 Euro",
        "Commissioni 1,00 Euro Totale operazione",
        total,
    ]
    return [Element(1, "text", text, "body", False) for text in texts]


def test_claims_transfer() -> None:
    assert IntesaTransfer().is_this_yours(transfer()) is Claim.full


def test_parses_fields() -> None:
    parsed = IntesaTransfer().parse(transfer())
    assert parsed.kind == "receipt"
    assert parsed.validity is not None
    assert (parsed.validity.lower, parsed.validity.upper) == (date(2030, 10, 8), date(2030, 10, 8))
    assert parsed.fields == {
        "number": "INTER111",
        "executed_on": date(2030, 10, 8),
        "beneficiary": "SCUOLA DI MUSICA",
        "amount": Decimal("10.00"),
        "fee": Decimal("1.00"),
        "total_amount": Decimal("11.00"),
    }


def test_rejects_total_that_doesnt_add_up() -> None:
    with pytest.raises(ParseError, match="is not 11.01"):
        IntesaTransfer().parse(transfer("11,01 Euro"))
