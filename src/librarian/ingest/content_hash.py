import hashlib

from librarian.adapters.readers.element import Element


def content_hash(elements: list[Element]) -> str:
    return text_hash("\0".join(e.text for e in elements))


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
