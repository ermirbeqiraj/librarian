import base64
import os
from pathlib import Path

import httpx

from librarian.adapters.paid_calls import PaidCalls
from librarian.adapters.readers.document_bytes import document_bytes

URL = "https://api.mistral.ai/v1/ocr"
MODEL = "mistral-ocr-latest"


def read_text(pdf: Path) -> str:
    return "\n\n".join(read_pages(pdf))


def read_pages(pdf: Path, paid_calls: PaidCalls | None = None) -> list[str]:
    encoded = base64.b64encode(document_bytes(pdf)).decode()
    client = httpx.Client(timeout=300)
    if paid_calls is not None:
        paid_calls.watch(client)
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
    pages: list[str] = []
    for page in response.json()["pages"]:
        pages.append(page["markdown"])
    return pages
