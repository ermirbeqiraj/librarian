from dataclasses import dataclass


@dataclass(frozen=True)
class Element:
    page: int
    kind: str
    text: str
    layer: str
    in_picture: bool
