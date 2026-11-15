from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from librarian.models.document_kind import DocumentKind


@dataclass(frozen=True)
class GasBill:
    number: str
    issued_on: date
    total_amount: Decimal
    consumption_smc: Decimal
    service: str = "gas"


@dataclass(frozen=True)
class ElectricityBill:
    number: str
    issued_on: date
    total_amount: Decimal
    consumption_kwh: Decimal
    service: str = "electricity"


@dataclass(frozen=True)
class PhoneBill:
    number: str
    issued_on: date
    total_amount: Decimal
    service: str = "phone"


# One name per fact, whichever path reads the document: the parsers write only these names
# and the drafter's prompt gives them per kind. Where a parser exists its names won; the
# other names are the ones the drafter used most.
DESCRIPTIONS = {
    "issuer": "the company, office or person that issued the document.",
    "number": "the document's own identifier (invoice, receipt or policy number).",
    "issued_on": "the date the document was issued.",
    "due_on": "the deadline for paying it.",
    "total_amount": "the total to pay, or the total paid.",
    "service": "the utility it is for (water, gas, electricity, phone, internet).",
    "bill_type": "the type of bill, as the document states it.",
    "consumption_smc": "the gas consumed in the billed period, in Smc.",
    "consumption_kwh": "the electricity consumed in the billed period, in kWh.",
    "consumption_mc": "the water consumed in the billed period, in mc.",
    "recipient": "the person or company the document is addressed to.",
    "concerns": "the person the document is about, when it is not the recipient (the student of"
    " a course, the patient of a visit).",
    "tax_code": "the recipient's codice fiscale.",
    "customer_code": "the recipient's customer number with the issuer.",
    "contract_code": "the number of the contract the document belongs to.",
    "payment_method": "how it is or was paid (direct debit, bank transfer, cash, card).",
    "iban": "the bank account it is paid from or to.",
    "instalment_1_date": "the first instalment's due date.",
    "instalment_1_amount": "the first instalment's amount.",
    "instalment_2_date": "the second instalment's due date; further ones numbered the same way,"
    " in date order.",
    "instalment_2_amount": "the second instalment's amount; further ones numbered the same way.",
    "annual_consumption": "the consumption over the last year, when stated.",
    "annual_spend": "the spending over the last year, when stated.",
    "supply_address": "the address where the service is supplied, when it differs from the"
    " recipient's.",
    "supply_point_code": "the code of the supply point (POD for electricity, PDR for gas).",
    "meter_number": "the meter's serial number (matricola).",
    "offer_name": "the name of the offer, tariff or plan.",
    "offer_ends_on": "the date the offer's price conditions end.",
    "distributor": "the company that runs the network (distributore).",
    "customer_service_phone": "the issuer's customer service number.",
    "emergency_phone": "the number for faults and emergencies (pronto intervento).",
    "vat_amount": "the total VAT charged.",
    "direct_debit_mandate": "the code of the direct debit mandate (SDD).",
    "previous_bills_paid": "whether the document says earlier bills are paid (yes or no).",
    "billing_frequency": "how often bills are issued (monthly, bimonthly...).",
    "next_bill_on": "the date the next bill will be issued.",
    "issuer_phone": "the issuer's phone number.",
    "issuer_address": "the issuer's address.",
    "issuer_website": "the issuer's website.",
}

FIELDS: dict[DocumentKind, list[str]] = {
    DocumentKind.invoice: [
        "issuer",
        "number",
        "issued_on",
        "due_on",
        "total_amount",
        "service",
        "bill_type",
        "consumption_smc",
        "consumption_kwh",
        "consumption_mc",
        "recipient",
        "concerns",
        "tax_code",
        "customer_code",
        "contract_code",
        "payment_method",
        "iban",
        "instalment_1_date",
        "instalment_1_amount",
        "instalment_2_date",
        "instalment_2_amount",
        "annual_consumption",
        "annual_spend",
        "supply_address",
        "supply_point_code",
        "meter_number",
        "offer_name",
        "offer_ends_on",
        "distributor",
        "customer_service_phone",
        "emergency_phone",
        "vat_amount",
        "direct_debit_mandate",
        "previous_bills_paid",
        "billing_frequency",
        "next_bill_on",
    ],
    DocumentKind.receipt: [
        "issuer",
        "number",
        "issued_on",
        "total_amount",
        "service",
        "recipient",
        "concerns",
        "tax_code",
        "payment_method",
        "iban",
        "vat_amount",
        "instalment_1_date",
        "instalment_1_amount",
        "instalment_2_date",
        "instalment_2_amount",
    ],
    DocumentKind.contract: [
        "issuer",
        "issued_on",
        "contract_code",
        "offer_name",
        "recipient",
        "concerns",
        "customer_service_phone",
        "issuer_phone",
        "issuer_address",
        "issuer_website",
    ],
}
