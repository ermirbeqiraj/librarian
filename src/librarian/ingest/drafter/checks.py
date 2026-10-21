import re
from dataclasses import dataclass

from librarian.ingest.drafter.schema import Draft, Validity

SPACES = re.compile(r"\s+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
QUOTED_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


@dataclass(frozen=True)
class Problem:
    field: str
    message: str


def problems(draft: Draft, text: str) -> list[Problem]:
    page = _flat(text)
    found: list[Problem] = []

    validity = draft.validity
    if _flat(validity.as_written) not in page:
        found.append(Problem("validity", f"{validity.as_written!r} is not in the document"))
    found.extend(_validity_dates(validity))

    for field in draft.fields:
        if _flat(field.as_written) not in page:
            found.append(Problem(field.name, f"{field.as_written!r} is not in the document"))
        if not _same_date(field.value, field.as_written):
            found.append(Problem(field.name, _mismatch(field.value, field.as_written)))
    return found


def _validity_dates(validity: Validity) -> list[Problem]:
    quoted = _quoted_dates(validity.as_written)
    start = validity.start.isoformat()
    end = None
    if validity.end is not None:
        end = validity.end.isoformat()

    found: list[Problem] = []
    if len(quoted) >= 2:
        if start not in quoted:
            found.append(Problem("validity.start", _mismatch(start, validity.as_written)))
        if end is not None and end not in quoted:
            found.append(Problem("validity.end", _mismatch(end, validity.as_written)))
    if len(quoted) == 1 and quoted[0] not in (start, end):
        message = f"neither start nor end is {quoted[0]}, the date in {validity.as_written!r}"
        found.append(Problem("validity", message))
    return found


def _same_date(value: str, quote: str) -> bool:
    quoted = _quoted_dates(quote)
    if not DATE.fullmatch(value) or not quoted:
        return True
    return value in quoted


def _quoted_dates(quote: str) -> list[str]:
    dates: list[str] = []
    for day, month, year in QUOTED_DATE.findall(quote):
        dates.append(f"{year}-{month}-{day}")
    return dates


def _mismatch(value: object, quote: str) -> str:
    return f"the value {value} does not match its text {quote!r}"


def _flat(text: str) -> str:
    return SPACES.sub(" ", text.replace("|", " ").replace("*", "")).strip()
