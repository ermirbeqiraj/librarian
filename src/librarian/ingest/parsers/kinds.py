from dataclasses import dataclass
from datetime import date
from decimal import Decimal


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


@dataclass(frozen=True)
class BankTransfer:
    number: str
    executed_on: date
    beneficiary: str
    amount: Decimal
    fee: Decimal
    total_amount: Decimal
