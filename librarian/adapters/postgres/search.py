"""Keyword and vector search over the chunks, merged and returned as whole sections.

One SQL query: top 50 chunks by keyword (`websearch_to_tsquery` over the unaccented
`search_text`), top 50 by cosine distance, merged with Reciprocal Rank Fusion (k = 60).
Each chunk hit is swapped for its section, sections are deduped and rank by their best
chunk; the top `limit` sections come back.
"""

from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from librarian.application.ingest import document
from librarian.application.ingest.ports import Embedder
from librarian.application.retrieve.period import Period, PeriodOp
from librarian.application.retrieve.ports import Hit, Mode

TOP_PER_SIDE = 50
RRF_K = 60


class PostgresSearch:
    def __init__(self, sessions: sessionmaker[Session], embedder: Embedder) -> None:
        self.sessions = sessions
        self.embedder = embedder

    def search(
        self,
        query: str,
        period: Period | None = None,
        kind: str | None = None,
        document_ids: Iterable[int] | None = None,
        limit: int = 5,
        mode: Mode = "hybrid",
    ) -> list[Hit]:
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
            params["vector"] = _vector_literal(self.embedder.embed([query])[0])
        with self.sessions() as session:
            rows = session.execute(text(_sql(mode, filters)), params).mappings().all()
        hits: list[Hit] = []
        for row in rows:
            hits.append(_hit(row))
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
        # Documents with no validity always pass.
        clauses.append(f"(d.validity IS NULL OR {_period_sql(period)})")
        params["period_start"] = period.start
        params["period_end"] = period.day_after
    fragment = " AND " + " AND ".join(clauses) if clauses else ""
    return fragment, params


def _period_sql(period: Period) -> str:
    """The period's predicate on `d.validity`, a daterange stored as [start, end)."""
    if period.op is PeriodOp.during:
        return "d.validity && daterange(:period_start, :period_end, '[)')"
    if period.op is PeriodOp.after:
        return "d.validity && daterange(:period_end, NULL, '[)')"
    if period.op is PeriodOp.before:
        return "d.validity && daterange(NULL, :period_start, '[)')"
    return "d.validity @> CAST(:period_start AS date)"


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


def _hit(row: Any) -> Hit:
    return Hit(
        section_id=row["section_id"],
        document_id=row["document_id"],
        kind=row["kind"],
        issuer=row["issuer"],
        validity=_validity(row["validity"]),
        heading=row["heading"],
        text=row["text"],
        chunk_text=row["chunk_text"],
        verified=row["verified"],
        keyword_rank=row["keyword_rank"],
        vector_rank=row["vector_rank"],
    )


def _validity(value: Any) -> document.Period | None:
    """Postgres gives a daterange back as [start, end): the end becomes the last day."""
    if value is None:
        return None
    end = value.upper
    if end is not None and not value.upper_inc:
        end = end - timedelta(days=1)
    return document.Period(value.lower, end)
