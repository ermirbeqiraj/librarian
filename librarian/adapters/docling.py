import atexit
from pathlib import Path

import httpx
from docling_core.types.doc.common.content_layer import ContentLayer
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.table.table import TableItem
from docling_core.types.doc.items.text import TextItem

from librarian.adapters.document_bytes import document_bytes
from librarian.application.ingest.element import Element
from librarian.application.ingest.paid_calls import PaidCalls


class Docling:
    """A PDF read by docling-serve, its own OCR off: free, it spends no paid calls."""

    def __init__(self, url: str) -> None:
        self.client = httpx.Client(base_url=url, timeout=300)
        atexit.register(self.client.close)

    def read(self, path: Path, paid_calls: PaidCalls | None = None) -> list[Element]:
        doc = self._convert(path)
        elements: list[Element] = []
        for item, _ in doc.iterate_items(
            traverse_pictures=True, included_content_layers=set(ContentLayer)
        ):
            if isinstance(item, TableItem):
                text = item.export_to_markdown(doc=doc)
            elif isinstance(item, TextItem):
                text = item.text
            else:
                continue
            if not item.prov:
                continue
            in_picture = bool(item.parent and item.parent.cref.startswith("#/pictures"))
            elements.append(
                Element(
                    item.prov[0].page_no,
                    item.label.value,
                    text,
                    item.content_layer.value,
                    in_picture,
                )
            )
        return elements

    def _convert(self, path: Path) -> DoclingDocument:
        response = self.client.post(
            "/v1/convert/file",
            files={"files": (path.name, document_bytes(path), "application/pdf")},
            data={"to_formats": "json", "do_ocr": "false"},
        )
        response.raise_for_status()
        return DoclingDocument.model_validate(response.json()["document"]["json_content"])
