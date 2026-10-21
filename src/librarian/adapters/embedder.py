import httpx

from librarian.config import EMBEDDER_URL

MODEL = "bge-m3"
LIMIT = 8192
MARGIN = 16
BATCH = 32


def count_tokens(text: str, url: str = EMBEDDER_URL) -> int:
    if text.strip() == "":
        return 0
    response = httpx.post(url + "/tokenize", json={"inputs": text, "add_special_tokens": False})
    response.raise_for_status()
    return len(response.json()[0])


def embed(texts: list[str], url: str = EMBEDDER_URL) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        response = httpx.post(
            url + "/embed", json={"inputs": texts[start : start + BATCH]}, timeout=300
        )
        response.raise_for_status()
        vectors.extend(response.json())
    return vectors
