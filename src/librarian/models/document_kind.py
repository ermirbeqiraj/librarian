from enum import StrEnum, auto


class DocumentKind(StrEnum):
    invoice = auto()
    receipt = auto()
    bank_statement = auto()
    payslip = auto()
    contract = auto()
    identity_document = auto()
    ticket = auto()
    other = auto()
