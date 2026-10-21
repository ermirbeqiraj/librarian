import re
from collections.abc import Callable
from dataclasses import dataclass

from librarian.adapters.readers.element import Element

HEADING = re.compile(r"^#+\s+(.+)$")
IMAGE = re.compile(r"^!\[[^\]]*\]\([^)]*\)$")


@dataclass(frozen=True)
class Section:
    heading: str
    page: int
    text: str


def split(elements: list[Element], is_heading: Callable[[Element], bool]) -> list[Section]:
    groups: list[tuple[Element | None, list[Element]]] = []
    seen: set[str] = set()
    for e in elements:
        if is_heading(e) and e.text not in seen:
            seen.add(e.text)
            groups.append((e, []))
        elif groups:
            groups[-1][1].append(e)
        else:
            groups.append((None, [e]))
    return [_section(heading, body) for heading, body in groups]


def _section(heading: Element | None, body: list[Element]) -> Section:
    text = "\n\n".join(e.text for e in body)
    if heading is None:
        return Section("", body[0].page, text)
    return Section(heading.text, heading.page, text)


def from_docling(elements: list[Element]) -> list[Section]:
    body = [e for e in elements if e.layer == "body"]
    return split(body, lambda e: e.kind == "section_header")


def from_markdown(pages: list[str]) -> list[Section]:
    """Sections of OCR markdown, one page per item: a # line opens a section."""
    sections: list[Section] = []
    seen: set[str] = set()
    heading = ""
    page = 1
    lines: list[str] = []
    for number, markdown in enumerate(pages, start=1):
        for line in markdown.splitlines():
            match = HEADING.match(line.strip())
            if match and match.group(1).strip() not in seen:
                if heading or "".join(lines).strip():
                    sections.append(Section(heading, page, "\n".join(lines).strip()))
                heading = match.group(1).strip()
                seen.add(heading)
                page = number
                lines = []
            elif not IMAGE.match(line.strip()):
                lines.append(line)
        lines.append("")
    if heading or "".join(lines).strip():
        sections.append(Section(heading, page, "\n".join(lines).strip()))
    return sections
