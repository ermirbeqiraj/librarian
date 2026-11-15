import base64
import os
from pathlib import Path

import httpx

from librarian.adapters.document_bytes import document_bytes
from librarian.adapters.mistral import watch
from librarian.application.ingest.element import Element
from librarian.application.ingest.paid_calls import PaidCalls

URL = "https://api.mistral.ai/v1/ocr"
MODEL = "mistral-ocr-latest"


class MistralOcr:
    """A PDF read by Mistral OCR: one element per page, its text the page's markdown."""

    def read(self, path: Path, paid_calls: PaidCalls | None = None) -> list[Element]:
        encoded = base64.b64encode(document_bytes(path)).decode()
        client = httpx.Client(timeout=300)
        if paid_calls is not None:
            watch(client, paid_calls)
        with client:
            response = client.post(
                URL,
                headers={"Authorization": f"Bearer {os.environ['MISTRAL_API_KEY']}"},
                json={
                    "model": MODEL,
                    "document": {
                        "type": "document_url",
                        "document_url": f"data:application/pdf;base64,{encoded}",
                    },
                },
            )
        response.raise_for_status()
        pages: list[Element] = []
        for number, page in enumerate(response.json()["pages"], start=1):
            pages.append(Element(number, "page", page["markdown"], "body", False))
        return pages
