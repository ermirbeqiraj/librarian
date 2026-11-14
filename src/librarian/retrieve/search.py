"""Keyword and vector search over the chunks, merged and returned as whole sections.

One SQL query: top 50 chunks by keyword (`websearch_to_tsquery` over the unaccented
`search_text`), top 50 by cosine distance, merged with Reciprocal Rank Fusion (k = 60).
Each chunk hit is swapped for its section, sections are deduped and rank by their best
chunk; the top `limit` sections come back.
"""

import re
from collections.abc import Iterable
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import Range

from librarian.adapters import embedder
from librarian.db import Session
from librarian.retrieve.period import Period

TOP_PER_SIDE = 50
RRF_K = 60
TRIM_LIMIT = 2000
TRIM_MARKER = "[…]"

Mode = Literal["keyword", "vector", "hybrid"]

# For the trim anchor: an unaccented term also matches its accented spelling
# ("perche" ~ "perché").
ACCENTED = {"a": "aàáâãäå", "e": "eèéêë", "i": "iìíîï", "o": "oòóôõö", "u": "uùúûü", "c": "cç"}


class Hit(BaseModel):
    """One returned section. A section in `seen` comes back as its id only (`is_ref`)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    section_id: int
    document_id: int | None = None
    kind: str | None = None
    issuer: str | None = None
    validity: Range[date] | None = None
    heading: str | None = None
    text: str | None = None
    verified: bool | None = None
    keyword_rank: int | None = None
    vector_rank: int | None = None

    @classmethod
    def ref(cls, section_id: int) -> "Hit":
        return cls(section_id=section_id)

    @property
    def is_ref(self) -> bool:
        return self.document_id is None


def search(
    query: str,
    period: Period | None = None,
    kind: str | None = None,
    document_ids: Iterable[int] | None = None,
    limit: int = 5,
    seen: Iterable[int] = (),
    mode: Mode = "hybrid",
    query_vector: list[float] | None = None,
) -> list[Hit]:
    """Search the chunks and return whole sections, best first.

    `mode` picks the sides that run; `query_vector` injects the query embedding (tests do
    that, so they don't need the embedder). Sections in `seen` come back as their id only.
    `document_ids` empty (an SQL step found no documents) means no hits, not all documents.
    """
    if mode not in ("keyword", "vector", "hybrid"):
        raise ValueError(f"unknown mode: {mode!r}")
    if limit < 1:
        raise ValueError(f"limit must be at least 1: {limit}")
    if document_ids is not None:
        document_ids = list(document_ids)
        if not document_ids:
            return []
    filters, params = _filters(period, kind, document_ids)
    params["query"] = query
    params["rrf_k"] = RRF_K
    params["limit"] = limit
    if mode != "keyword":
        if query_vector is None:
            query_vector = embedder.embed([query])[0]
        params["vector"] = _vector_literal(query_vector)
    with Session() as session:
        rows = session.execute(text(_sql(mode, filters)), params).mappings().all()
    seen_ids = set(seen)
    hits = []
    for row in rows:
        if row["section_id"] in seen_ids:
            hits.append(Hit.ref(row["section_id"]))
        else:
            hits.append(_hit(row, query))
    return hits


def _filters(
    period: Period | None, kind: str | None, document_ids: Iterable[int] | None
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if kind is not None:
        clauses.append("d.kind = :kind")
        params["kind"] = kind
    if document_ids is not None:
        clauses.append("s.document_id = ANY(:document_ids)")
        params["document_ids"] = list(document_ids)
    if period is not None:
        clause, period_params = period.filter_sql("d.validity")
        clauses.append(clause)
        params.update(period_params)
    fragment = " AND " + " AND ".join(clauses) if clauses else ""
    return fragment, params


def _sql(mode: Mode, filters: str) -> str:
    keyword = mode in ("keyword", "hybrid")
    vector = mode in ("vector", "hybrid")
    q = "q AS (SELECT websearch_to_tsquery('italian', unaccent_immutable(:query)) AS query"
    if vector:
        q += ", CAST(:vector AS vector) AS vector"
    q += "),"
    keyword_side = ""
    vector_side = ""
    if keyword:
        keyword_side = f"""
    kw AS (
        SELECT c.id AS chunk_id, c.document_section_id, ts_rank(c.search_text, q.query) AS score
        FROM chunks c
        JOIN document_sections s ON s.id = c.document_section_id
        JOIN documents d ON d.id = s.document_id
        CROSS JOIN q
        WHERE c.search_text @@ q.query{filters}
        ORDER BY score DESC, c.id
        LIMIT {TOP_PER_SIDE}
    ),
    kw_ranked AS (
        SELECT chunk_id, document_section_id,
               row_number() OVER (ORDER BY score DESC, chunk_id) AS keyword_rank
        FROM kw
    ),"""
    if vector:
        vector_side = f"""
    vec AS (
        SELECT c.id AS chunk_id, c.document_section_id, c.embedding <=> q.vector AS distance
        FROM chunks c
        JOIN document_sections s ON s.id = c.document_section_id
        JOIN documents d ON d.id = s.document_id
        CROSS JOIN q
        WHERE true{filters}
        ORDER BY distance, c.id
        LIMIT {TOP_PER_SIDE}
    ),
    vec_ranked AS (
        SELECT chunk_id, document_section_id,
               row_number() OVER (ORDER BY distance, chunk_id) AS vector_rank
        FROM vec
    ),"""
    if keyword and vector:
        hits = """
    hits AS (
        SELECT coalesce(k.chunk_id, v.chunk_id) AS chunk_id,
               coalesce(k.document_section_id, v.document_section_id) AS section_id,
               k.keyword_rank, v.vector_rank
        FROM kw_ranked k FULL OUTER JOIN vec_ranked v ON v.chunk_id = k.chunk_id
    ),"""
    elif keyword:
        hits = """
    hits AS (
        SELECT chunk_id, document_section_id AS section_id, keyword_rank,
               NULL::int AS vector_rank
        FROM kw_ranked
    ),"""
    else:
        hits = """
    hits AS (
        SELECT chunk_id, document_section_id AS section_id, NULL::int AS keyword_rank,
               vector_rank
        FROM vec_ranked
    ),"""
    return f"""
WITH {q}
{keyword_side}
{vector_side}
{hits}
    chunk_scores AS (
        SELECT section_id, chunk_id, keyword_rank, vector_rank,
               coalesce(1.0 / (:rrf_k + keyword_rank), 0)
             + coalesce(1.0 / (:rrf_k + vector_rank), 0) AS rrf
        FROM hits
    ),
    best AS (
        SELECT DISTINCT ON (section_id) section_id, chunk_id, keyword_rank, vector_rank, rrf
        FROM chunk_scores
        ORDER BY section_id, rrf DESC, chunk_id
    ),
    top_sections AS (
        SELECT section_id, chunk_id, keyword_rank, vector_rank, rrf
        FROM best
        ORDER BY rrf DESC, section_id
        LIMIT :limit
    )
SELECT t.section_id, t.chunk_id, t.keyword_rank, t.vector_rank,
       s.document_id, s.heading, s.text,
       d.kind, d.fields ->> 'issuer' AS issuer, d.validity,
       d.status = 'confirmed' AS verified,
       c.text AS chunk_text
FROM top_sections t
JOIN document_sections s ON s.id = t.section_id
JOIN documents d ON d.id = s.document_id
JOIN chunks c ON c.id = t.chunk_id
ORDER BY t.rrf DESC, t.section_id
"""


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _hit(row: Any, query: str) -> Hit:
    text: str = row["text"]
    if len(text) > TRIM_LIMIT:
        text = _window(text, _anchor(text, row["chunk_text"], query))
    return Hit(
        section_id=row["section_id"],
        document_id=row["document_id"],
        kind=row["kind"],
        issuer=row["issuer"],
        validity=_as_range(row["validity"]),
        heading=row["heading"],
        text=text,
        verified=row["verified"],
        keyword_rank=row["keyword_rank"],
        vector_rank=row["vector_rank"],
    )


def _as_range(value: Any) -> Range[date] | None:
    if value is None:
        return None
    return Range(value.lower, value.upper, bounds=value.bounds)


def _anchor(text: str, chunk_text: str, query: str) -> int:
    """Where to center the trim window.

    bge-m3 chunks a section whole (one chunk per section, its budget is 8192 tokens), so
    there is usually no best chunk to trim around: anchor on the first query term in the
    text instead. Otherwise anchor on the best chunk's place in the section.
    """
    earliest: int | None = None
    for term in re.findall(r"\w+", query, re.UNICODE):
        if len(term) < 3:
            continue
        match = _term_pattern(term).search(text)
        if match is not None and (earliest is None or match.start() < earliest):
            earliest = match.start()
    if earliest is not None:
        return earliest
    position = _locate(text, chunk_text)
    if position is not None:
        return position
    return len(text) // 2


def _term_pattern(term: str) -> re.Pattern[str]:
    chars = []
    for char in term.lower():
        group = ACCENTED.get(char, char)
        chars.append(f"[{re.escape(group)}{re.escape(group.upper())}]")
    return re.compile(r"\b" + "".join(chars) + r"\b", re.IGNORECASE)


def _locate(haystack: str, needle: str) -> int | None:
    """Start of the chunk's body in the section text, whitespace ignored, or None."""
    body = needle.split("\n", 1)[1] if "\n" in needle else needle
    squeezed, index = _squeeze_with_index(haystack)
    position = squeezed.find(re.sub(r"\s+", " ", body).strip())
    if position < 0:
        return None
    return index[min(position, len(index) - 1)]


def _squeeze_with_index(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index: list[int] = []
    previous_space = True
    for position, char in enumerate(text):
        if char.isspace():
            if not previous_space and chars:
                chars.append(" ")
                index.append(position)
            previous_space = True
        else:
            chars.append(char)
            index.append(position)
            previous_space = False
    return "".join(chars), index


def _window(text: str, anchor: int, limit: int = TRIM_LIMIT) -> str:
    """`limit` characters around the anchor, marked `[…]` where it was cut."""
    start = max(0, min(anchor - limit // 2, len(text) - limit))
    end = start + limit
    prefix = TRIM_MARKER if start > 0 else ""
    suffix = TRIM_MARKER if end < len(text) else ""
    return prefix + text[start:end] + suffix
