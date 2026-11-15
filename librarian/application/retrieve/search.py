"""What a search hands the agent and the search eval: whole sections, best first, a long one
trimmed around the match, and a section already returned as its id only."""

import re
from collections.abc import Iterable

from librarian.application.retrieve.period import Period
from librarian.application.retrieve.ports import Hit, Mode, Search

TRIM_LIMIT = 2000
TRIM_MARKER = "[…]"

# For the trim anchor: an unaccented term also matches its accented spelling
# ("perche" ~ "perché").
ACCENTED = {"a": "aàáâãäå", "e": "eèéêë", "i": "iìíîï", "o": "oòóôõö", "u": "uùúûü", "c": "cç"}


def search(
    sections: Search,
    query: str,
    period: Period | None = None,
    kind: str | None = None,
    document_ids: Iterable[int] | None = None,
    limit: int = 5,
    seen: Iterable[int] = (),
    mode: Mode = "hybrid",
) -> list[Hit]:
    """The top `limit` sections; those in `seen` come back as their id only."""
    seen_ids = set(seen)
    hits: list[Hit] = []
    for hit in sections.search(query, period, kind, document_ids, limit, mode):
        if hit.section_id in seen_ids:
            hits.append(Hit.ref(hit.section_id))
        else:
            hits.append(_trimmed(hit, query))
    return hits


def _trimmed(hit: Hit, query: str) -> Hit:
    if hit.text is None or len(hit.text) <= TRIM_LIMIT:
        return hit
    text = _window(hit.text, _anchor(hit.text, hit.chunk_text or "", query))
    return hit.model_copy(update={"text": text})


def _anchor(text: str, chunk_text: str, query: str) -> int:
    """Where to center the trim window.

    A section usually fits in one chunk, so there is no best chunk to trim around: anchor on
    the first query term in the text instead. Otherwise anchor on the best chunk's place in
    the section.
    """
    earliest: int | None = None
    for term in re.findall(r"\w+", query, re.UNICODE):
        if len(term) < 3:
            continue
        match = _term_pattern(term).search(text)
        if match is not None and (earliest is None or match.start() < earliest):
            earliest = match.start()
    if earliest is not None:
        return earliest
    position = _locate(text, chunk_text)
    if position is not None:
        return position
    return len(text) // 2


def _term_pattern(term: str) -> re.Pattern[str]:
    chars = []
    for char in term.lower():
        group = ACCENTED.get(char, char)
        chars.append(f"[{re.escape(group)}{re.escape(group.upper())}]")
    return re.compile(r"\b" + "".join(chars) + r"\b", re.IGNORECASE)


def _locate(haystack: str, needle: str) -> int | None:
    """Start of the chunk's body in the section text, whitespace ignored, or None."""
    body = needle.split("\n", 1)[1] if "\n" in needle else needle
    squeezed, index = _squeeze_with_index(haystack)
    position = squeezed.find(re.sub(r"\s+", " ", body).strip())
    if position < 0:
        return None
    return index[min(position, len(index) - 1)]


def _squeeze_with_index(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index: list[int] = []
    previous_space = True
    for position, char in enumerate(text):
        if char.isspace():
            if not previous_space and chars:
                chars.append(" ")
                index.append(position)
            previous_space = True
        else:
            chars.append(char)
            index.append(position)
            previous_space = False
    return "".join(chars), index


def _window(text: str, anchor: int, limit: int = TRIM_LIMIT) -> str:
    """`limit` characters around the anchor, marked `[…]` where it was cut."""
    start = max(0, min(anchor - limit // 2, len(text) - limit))
    end = start + limit
    prefix = TRIM_MARKER if start > 0 else ""
    suffix = TRIM_MARKER if end < len(text) else ""
    return prefix + text[start:end] + suffix
