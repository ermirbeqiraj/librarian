import re
from collections.abc import Callable

from librarian.ingest.parsers.sections import Section

SENTENCE = re.compile(r"(?<=[.?!]) ")
COMMA = re.compile(r"(?<=,) ")
WORD = re.compile(r" ")
SPLITTERS = [SENTENCE, COMMA, WORD]


def chunk(section: Section, budget: int, size: Callable[[str], int]) -> list[str]:
    room = budget - size(section.heading)

    pieces: list[str] = []
    for paragraph in section.text.split("\n\n"):
        if paragraph.strip() == "":
            continue
        pieces.extend(_fit(paragraph, room, size, 0))

    groups: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    for piece in pieces:
        piece_size = size(piece)
        if current and current_size + piece_size > room:
            groups.append(current)
            current = []
            current_size = 0
        current.append(piece)
        current_size += piece_size
    if current:
        groups.append(current)

    chunks: list[str] = []
    for group in groups:
        chunks.append(section.heading + "\n" + " ".join(group))
    return chunks


def _fit(text: str, room: int, size: Callable[[str], int], level: int) -> list[str]:
    if size(text) <= room:
        return [text]
    if level == len(SPLITTERS):
        return [text]
    pieces: list[str] = []
    for part in SPLITTERS[level].split(text):
        pieces.extend(_fit(part, room, size, level + 1))
    return pieces
