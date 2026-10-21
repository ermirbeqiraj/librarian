from datetime import date

from librarian.ingest.drafter.checks import Problem, problems
from librarian.ingest.drafter.schema import DocumentField, Draft, Validity
from librarian.models.document_kind import DocumentKind

PAGE = """Ricevuta del 05/10/2030

| Corso valido dal 07/10/2030 al   05/05/2031 |   |

| Totale Documento | 1.235,00 € |
| Pagamento | BONIFICO BANCARIO |"""


def draft(fields: list[DocumentField], start: date = date(2030, 10, 7)) -> Draft:
    validity = Validity(
        start=start, end=date(2031, 5, 5), as_written="dal 07/10/2030 al 05/05/2031"
    )
    return Draft(kind=DocumentKind.receipt, validity=validity, fields=fields, description="")


def field(value: str, as_written: str) -> DocumentField:
    return DocumentField(name="f", value=value, as_written=as_written)


def test_faithful_draft_has_no_problems() -> None:
    fields = [
        field("2030-10-05", "Ricevuta del 05/10/2030"),
        field("1235.00", "Totale Documento 1.235,00 €"),
        field("bank_transfer", "BONIFICO BANCARIO"),
    ]
    assert problems(draft(fields), PAGE) == []


def test_quote_not_in_the_document() -> None:
    assert problems(draft([field("10.00", "Totale 10,00 €")]), PAGE) == [
        Problem("f", "'Totale 10,00 €' is not in the document"),
    ]


def test_date_that_disagrees_with_its_quote() -> None:
    assert problems(draft([], start=date(2030, 10, 5)), PAGE) == [
        Problem(
            "validity.start",
            "the value 2030-10-05 does not match its text 'dal 07/10/2030 al 05/05/2031'",
        )
    ]


def test_one_quoted_date_must_be_a_bound_and_the_other_is_free() -> None:
    page = "SCADENZA 31/08/2031 VALIDITA' 12 MESI"
    validity = Validity(start=date(2030, 9, 1), end=date(2031, 8, 31), as_written=page)
    fine = Draft(kind=DocumentKind.receipt, validity=validity, fields=[], description="")
    assert problems(fine, page) == []

    wrong = validity.model_copy(update={"end": date(2032, 8, 31)})
    assert problems(fine.model_copy(update={"validity": wrong}), page) == [
        Problem("validity", f"neither start nor end is 2031-08-31, the date in {page!r}"),
    ]


def test_markdown_bold_does_not_hide_a_quote() -> None:
    page = "IBAN : **IT00X0000000000000000000000**"
    fields = [field("IT00X0000000000000000000000", "IBAN : IT00X0000000000000000000000")]
    assert problems(draft(fields), page + "\ndal 07/10/2030 al 05/05/2031") == []
