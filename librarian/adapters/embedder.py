import httpx

MODEL = "bge-m3"
LIMIT = 8192
MARGIN = 16
BATCH = 32


class TeiEmbedder:
    """bge-m3 behind Text Embeddings Inference."""

    model = MODEL
    budget = LIMIT - MARGIN

    def __init__(self, url: str) -> None:
        self.url = url

    def count_tokens(self, text: str) -> int:
        if text.strip() == "":
            return 0
        response = httpx.post(
            self.url + "/tokenize", json={"inputs": text, "add_special_tokens": False}
        )
        response.raise_for_status()
        return len(response.json()[0])

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            response = httpx.post(
                self.url + "/embed", json={"inputs": texts[start : start + BATCH]}, timeout=300
            )
            response.raise_for_status()
            vectors.extend(response.json())
        return vectors
