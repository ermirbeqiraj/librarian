import base64
import os
from pathlib import Path

import httpx

URL = "https://api.mistral.ai/v1/ocr"
MODEL = "mistral-ocr-latest"


def read_text(pdf: Path) -> str:
    return "\n\n".join(read_pages(pdf))


def read_pages(pdf: Path) -> list[str]:
    encoded = base64.b64encode(pdf.read_bytes()).decode()
    response = httpx.post(
        URL,
        headers={"Authorization": f"Bearer {os.environ['MISTRAL_API_KEY']}"},
        json={
            "model": MODEL,
            "document": {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{encoded}",
            },
        },
        timeout=300,
    )
    response.raise_for_status()
    pages: list[str] = []
    for page in response.json()["pages"]:
        pages.append(page["markdown"])
    return pages
