from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.layouts.cogeide_water import CogeideWater
from librarian.ingest.parsers.layouts.duferco_electricity import DufercoElectricity
from librarian.ingest.parsers.layouts.hera import Hera
from librarian.ingest.parsers.layouts.hera_2025 import Hera2025
from librarian.ingest.parsers.layouts.intesa_transfer import IntesaTransfer
from librarian.ingest.parsers.layouts.tim import Tim
from librarian.ingest.parsers.parser import Claim, ParseError, Parser

PARSERS: list[Parser] = [
    CogeideWater(),
    Hera(),
    Hera2025(),
    DufercoElectricity(),
    Tim(),
    IntesaTransfer(),
]


class UnknownDocument(ParseError):
    pass


class UnknownLayout(ParseError):
    pass


def detect_parser(elements: list[Element], parsers: list[Parser] = PARSERS) -> Parser:
    claims = [(parser, parser.is_this_yours(elements)) for parser in parsers]
    full = [parser for parser, claim in claims if claim is Claim.full]
    if len(full) > 1:
        raise RuntimeError(f"more than one parser claims it: {full}")
    if full:
        return full[0]
    if any(claim is Claim.provider for _, claim in claims):
        raise UnknownLayout("known provider, unknown layout")
    raise UnknownDocument("no parser claims it")
