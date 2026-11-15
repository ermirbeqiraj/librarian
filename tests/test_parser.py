import pytest

from librarian.ingest.parsers.parser import Parsed, ParseError
from librarian.models.document_kind import DocumentKind


def test_a_parser_writes_only_its_kinds_fields() -> None:
    with pytest.raises(ParseError, match="'consumption' is not in the invoice field list"):
        Parsed(DocumentKind.invoice, None, {"issuer": "Stub S.p.A.", "consumption": "1"})


def test_a_kind_with_no_list_takes_no_fields() -> None:
    with pytest.raises(ParseError, match="'issuer' is not in the other field list"):
        Parsed(DocumentKind.other, None, {"issuer": "Stub S.p.A."})
