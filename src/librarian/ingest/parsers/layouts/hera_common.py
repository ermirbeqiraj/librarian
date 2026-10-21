import re
from decimal import Decimal

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.parser import ParseError
from librarian.ingest.parsers.values import italian_decimal, table_rows

PIVA = "03819031208"
QR_ROW = re.compile(r"(?=.*[a-z])(?=.+[A-Z])[A-Za-z0-9:;]{12,}")
PRINT_MARKER = "FirstPageCheck"
NOTES = "Comunicazioni"
SUMMARY = "Riepilogo"


def clean(elements: list[Element]) -> list[Element]:
    kept: list[Element] = []
    for e in elements:
        if e.layer != "body" or QR_ROW.fullmatch(e.text):
            continue
        text = e.text.split(PRINT_MARKER)[0].strip()
        if e.kind == "table":
            text = _without_repeated_cells(text)
        if text:
            kept.append(Element(e.page, e.kind, text, e.layer, e.in_picture))
    return kept


def with_notes_and_cover(elements: list[Element], cover_cue: str) -> list[Element]:
    cover_page = _cover_page(elements, cover_cue)
    notes = [e for e in elements if e.page < cover_page]
    rest = [e for e in elements if e.page >= cover_page]
    result: list[Element] = []
    if notes:
        result.append(heading(NOTES, notes[0].page))
        result.extend(notes)
    result.append(heading(SUMMARY, cover_page))
    result.extend(rest)
    return result


def heading(text: str, page: int) -> Element:
    return Element(page, "section_header", text, "body", False)


def table(elements: list[Element], first_cell: str) -> list[list[str]]:
    for e in elements:
        if e.kind == "table":
            rows = table_rows(e.text)
            if rows and label(rows[0][0]) == first_cell:
                return rows
    raise ParseError(f"hera: no table {first_cell!r}")


def amount(rows: list[list[str]], row_label: str, column: int = 0) -> Decimal:
    for row in rows:
        if label(row[column]) == row_label:
            return italian_decimal(row[column + 1])
    raise ParseError(f"hera: no row {row_label!r}")


def label(cell: str) -> str:
    return cell.rstrip(". ")


def after(elements: list[Element], text: str) -> str:
    for i in range(len(elements) - 1):
        if elements[i].text == text:
            return elements[i + 1].text
    raise ParseError(f"hera: nothing after {text!r}")


def _without_repeated_cells(markdown: str) -> str:
    lines: list[str] = []
    for row in table_rows(markdown):
        cells: list[str] = []
        for cell in row:
            if not cells or cells[-1] != cell:
                cells.append(cell)
        if cells != [""]:
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _cover_page(elements: list[Element], cover_cue: str) -> int:
    for e in elements:
        if cover_cue in e.text:
            return e.page
    raise ParseError("hera: no cover page")
