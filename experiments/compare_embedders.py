import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from librarian.adapters import embedder
from librarian.adapters.readers import docling_reader
from librarian.adapters.readers.element import Element
from librarian.ingest.chunks import chunk
from librarian.ingest.parsers.detect_parser import detect_parser
from librarian.ingest.parsers.sections import Section

CACHE_DIR = Path(__file__).parent.parent / ".docs" / "cache"
SAMPLES_DIR = Path.home() / "Dropbox" / "library" / "inbox"
QUESTION_FILES = sorted((Path.home() / "Dropbox" / "library" / "evals").glob("questions-*.json"))
RUNS_DIR = Path.home() / "Dropbox" / "library" / "learnings" / "evals" / "embedders"


@dataclass(frozen=True)
class Model:
    name: str
    url: str
    limit: int
    query_prefix: str
    passage_prefix: str


# Losers stay commented out, so a rerun can bring them back: see learnings/retrieval.md.
MODELS = [
    # Model("minilm", "http://127.0.0.1:8081", 128, "", ""),
    # Model("e5", "http://127.0.0.1:8082", 512, "query: ", "passage: "),
    Model("bge-m3", "http://127.0.0.1:8083", 8192, "", ""),
]


def main() -> None:
    ran_at = datetime.now()
    question_sets: list[dict[str, Any]] = []
    for questions_path in QUESTION_FILES:
        questions = json.loads(questions_path.read_text())
        document = questions[0]["document"]
        elements = load_elements(document)
        sections = detect_parser(elements).sections(elements)
        write_sections(document, sections)

        print(questions_path.name)
        results: list[dict[str, Any]] = []
        for model in MODELS:
            section_vectors = embed_sections(model, sections)
            answers: list[dict[str, Any]] = []
            ranks: list[int] = []
            for question in questions:
                rank = answer_rank(
                    model, question["question"], question["sections"], section_vectors
                )
                ranks.append(rank)
                answers.append(
                    {
                        "by": question.get("by"),
                        "question": question["question"],
                        "expected": question["sections"],
                        "rank": rank,
                    }
                )
            print(model.name, ranks)
            results.append({"model": model.name, "first": ranks.count(1), "answers": answers})

        question_sets.append(
            {
                "questions": questions_path.name,
                "document": document,
                "sections": len(sections),
                "results": results,
            }
        )

    models: list[dict[str, Any]] = []
    for model in MODELS:
        models.append(asdict(model))
    run = {
        "ran_at": ran_at.isoformat(timespec="seconds"),
        "input": {"commit": commit(), "models": models},
        "result": question_sets,
    }
    save(ran_at, run)


def load_elements(document: str) -> list[Element]:
    cache = CACHE_DIR / f"{Path(document).stem}.elements.json"
    if cache.exists():
        return TypeAdapter(list[Element]).validate_json(cache.read_text())
    elements = docling_reader.read(SAMPLES_DIR / document)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(elements, default=asdict))
    return elements


def write_sections(document: str, sections: list[Section]) -> None:
    text = ""
    for section in sections:
        text += f"=== p{section.page} {section.heading}\n{section.text}\n\n"
    (CACHE_DIR / f"{Path(document).stem}.sections.txt").write_text(text)


def embed_sections(model: Model, sections: list[Section]) -> dict[str, list[list[float]]]:
    section_vectors: dict[str, list[list[float]]] = {}
    for section in sections:
        texts: list[str] = []
        for piece in chunk(
            section, model.limit - embedder.MARGIN, lambda text: count_tokens(model, text)
        ):
            texts.append(model.passage_prefix + piece)
        if texts:
            section_vectors[section.heading] = embed(model, texts)
    return section_vectors


def answer_rank(
    model: Model,
    question: str,
    answer_headings: list[str],
    section_vectors: dict[str, list[list[float]]],
) -> int:
    question_vector = embed(model, [model.query_prefix + question])[0]

    section_scores: dict[str, float] = {}
    for heading, vectors in section_vectors.items():
        section_scores[heading] = best_score(question_vector, vectors)

    ranking = sorted(section_scores, key=lambda heading: section_scores[heading], reverse=True)
    for position, heading in enumerate(ranking, start=1):
        if heading in answer_headings:
            return position
    return 0


def best_score(question_vector: list[float], chunk_vectors: list[list[float]]) -> float:
    scores: list[float] = []
    for vector in chunk_vectors:
        scores.append(similarity(question_vector, vector))
    return max(scores)


def similarity(a: list[float], b: list[float]) -> float:
    total = 0.0
    for x, y in zip(a, b, strict=True):
        total += x * y
    return total


def count_tokens(model: Model, text: str) -> int:
    return embedder.count_tokens(text, model.url)


def embed(model: Model, texts: list[str]) -> list[list[float]]:
    return embedder.embed(texts, model.url)


def commit() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    changes = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if changes:
        return head + "-dirty"
    return head


def save(ran_at: datetime, run: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{ran_at:%Y-%m-%dT%H-%M-%S}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
