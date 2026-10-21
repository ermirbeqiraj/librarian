from datetime import date

from pydantic import BaseModel

from librarian.models.document_kind import DocumentKind


class Validity(BaseModel):
    start: date
    end: date | None
    as_written: str


class DocumentField(BaseModel):
    name: str
    value: str
    as_written: str


class Draft(BaseModel):
    kind: DocumentKind
    validity: Validity
    fields: list[DocumentField]
    description: str
