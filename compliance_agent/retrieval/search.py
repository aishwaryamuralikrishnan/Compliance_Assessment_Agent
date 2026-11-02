"""One query, three lookups, one fused list.

    embed_query      -> cosine nearest neighbours on legal_chunks.embedding (HNSW)
    to_tsquery       -> ranked keyword search on legal_chunks.tsv (GIN)
    parse_identifiers-> WHERE filters on the metadata columns ("Article 22(1)")

Reciprocal rank fusion merges the three lists: score = sum(1 / (60 + rank)). Identifier
hits get the best possible rank in their own list, so a chunk the user named explicitly
always surfaces. The result carries every per-source rank for the run trace.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langsmith import traceable

from .. import db
from ..models import embeddings
from .identifiers import IdentifierFilter, parse_identifiers

RRF_K = 60
COLUMNS = """id, chunk_key, regulation, unit_type, chapter, chapter_title, section, section_title,
             article, article_letter, article_title, paragraph, paragraph_letter, recital,
             annex, annex_title, point, heading, text, cross_refs, word_count"""


@dataclass
class RetrievedChunk:
    id: int
    chunk_key: str
    regulation: str
    unit_type: str
    heading: str
    text: str
    article: int | None = None
    article_letter: str | None = None
    article_title: str | None = None
    paragraph: int | None = None
    paragraph_letter: str | None = None
    recital: int | None = None
    annex: str | None = None
    annex_title: str | None = None
    point: str | None = None
    chapter: str | None = None
    chapter_title: str | None = None
    section: str | None = None
    section_title: str | None = None
    cross_refs: list[int] = field(default_factory=list)
    word_count: int = 0
    # retrieval bookkeeping
    ranks: dict[str, int] = field(default_factory=dict)     # source -> 1-based rank
    fused_score: float = 0.0
    rerank_score: float | None = None
    vector_distance: float | None = None
    ts_rank: float | None = None
    grader_relevant: bool | None = None   # set by the retrieval loop: True = grader marked it relevant

    @property
    def citation(self) -> str:
        """Short form used in assessments, e.g. 'GDPR Art. 22(1)', 'AI Act Annex III 5', 'GDPR Rec. 71'."""
        reg = "GDPR" if self.regulation == "GDPR" else "AI Act"
        if self.recital is not None:
            return f"{reg} Rec. {self.recital}"
        if self.annex is not None:
            return f"{reg} Annex {self.annex}" + (f" point {self.point}" if self.point else "")
        art = f"{self.article}{self.article_letter or ''}"
        para = f"({self.paragraph}{self.paragraph_letter or ''})" if self.paragraph is not None else ""
        return f"{reg} Art. {art}{para}"

    def as_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id, "chunk_key": self.chunk_key, "citation": self.citation, "heading": self.heading,
            "regulation": self.regulation, "unit_type": self.unit_type, "text": self.text,
            "cross_refs": self.cross_refs, "ranks": self.ranks, "fused_score": round(self.fused_score, 5),
            "rerank_score": self.rerank_score, "grader_relevant": self.grader_relevant,
        }
        return d


def _row_to_chunk(row: dict[str, Any]) -> RetrievedChunk:
    return RetrievedChunk(
        id=row["id"], chunk_key=row["chunk_key"], regulation=row["regulation"], unit_type=row["unit_type"],
        heading=row["heading"], text=row["text"], article=row["article"], article_letter=row["article_letter"],
        article_title=row["article_title"], paragraph=row["paragraph"], paragraph_letter=row["paragraph_letter"],
        recital=row["recital"], annex=row["annex"], annex_title=row["annex_title"], point=row["point"],
        chapter=row["chapter"], chapter_title=row["chapter_title"], section=row["section"],
        section_title=row["section_title"], cross_refs=list(row["cross_refs"] or []), word_count=row["word_count"],
    )


def _reg_clause(regulation: str | None, params: list[Any]) -> str:
    if regulation:
        params.append(regulation)
        return " AND regulation = %s"
    return ""


# --------------------------------------------------------------------------------------
# The three lookups
# --------------------------------------------------------------------------------------

@traceable(name="vector_search", run_type="retriever")
def vector_search(query: str, k: int = 20, regulation: str | None = None) -> list[RetrievedChunk]:
    vec = embeddings().embed_query(query)
    params: list[Any] = []
    reg = _reg_clause(regulation, params)
    sql = f"""
        SELECT {COLUMNS}, embedding <=> %s::vector AS distance
        FROM legal_chunks
        WHERE embedding IS NOT NULL {reg}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with db.connection() as conn:
        rows = conn.execute(sql, [vec, *params, vec, k]).fetchall()
    out = []
    for i, r in enumerate(rows, start=1):
        c = _row_to_chunk(r)
        c.vector_distance = float(r["distance"])
        c.ranks["vector"] = i
        out.append(c)
    return out


@traceable(name="fulltext_search", run_type="retriever")
def fulltext_search(query: str, k: int = 20, regulation: str | None = None) -> list[RetrievedChunk]:
    # OR-semantics keyword query ranked by match density: a chunk that contains three of the
    # five query terms still scores, instead of requiring every term (websearch_to_tsquery ANDs).
    # Ordering: number of distinct query terms matched first (so a chunk matching three of
    # four terms beats one matching a single generic word in its heading), then
    # ts_rank_cd with normalisation 4 (query terms occurring close together score higher).
    with db.connection() as conn:
        tsq_text = conn.execute("SELECT plainto_tsquery('english', %s)::text AS t", [query]).fetchone()["t"]
        if not tsq_text:
            return []
        lexemes = [t.strip() for t in tsq_text.split(" & ") if t.strip()]
        or_query = " | ".join(lexemes)
        params: list[Any] = [or_query, lexemes]
        reg = _reg_clause(regulation, params)
        sql = f"""
            WITH q AS (SELECT %s::tsquery AS tsq, %s::text[] AS lex)
            SELECT {COLUMNS},
                   (SELECT count(*) FROM unnest(q.lex) l WHERE tsv @@ l::tsquery) AS matched,
                   ts_rank_cd(tsv, q.tsq, 4) AS rank
            FROM legal_chunks, q
            WHERE tsv @@ q.tsq {reg}
            ORDER BY matched DESC, rank DESC
            LIMIT %s
        """
        rows = conn.execute(sql, [*params, k]).fetchall()
    out = []
    for i, r in enumerate(rows, start=1):
        c = _row_to_chunk(r)
        c.ts_rank = float(r["rank"])
        c.ranks["fulltext"] = i
        out.append(c)
    return out


def fetch_by_identifier(f: IdentifierFilter) -> list[RetrievedChunk]:
    """Exact metadata lookup. Article without paragraph returns the whole article (all its chunks)."""
    where: list[str] = []
    params: list[Any] = []
    if f.regulation:
        where.append("regulation = %s"); params.append(f.regulation)
    if f.recital is not None:
        where.append("recital = %s"); params.append(f.recital)
    elif f.annex is not None:
        where.append("annex = %s"); params.append(f.annex)
        if f.point:
            where.append("(point = %s OR point LIKE %s)"); params.extend([f.point, f"%.{f.point}"])
    elif f.article is not None:
        where.append("article = %s"); params.append(f.article)
        where.append("article_letter IS NOT DISTINCT FROM %s"); params.append(f.article_letter)
        if f.paragraph is not None:
            where.append("(paragraph IS NULL OR (paragraph = %s AND paragraph_letter IS NOT DISTINCT FROM %s))")
            params.extend([f.paragraph, f.paragraph_letter])
    else:
        return []
    sql = f"SELECT {COLUMNS} FROM legal_chunks WHERE {' AND '.join(where)} ORDER BY regulation, article, paragraph, recital, annex, point"
    with db.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_chunk(r) for r in rows]


def fetch_by_reference(regulation: str, reference: str) -> list[RetrievedChunk]:
    """'Article 22(1)' / 'Art. 75a' / 'Recital 71' / 'Annex III point 5' -> chunks (for get_article + verify_citations)."""
    parsed = parse_identifiers(reference, default_regulation=regulation)
    out: list[RetrievedChunk] = []
    for f in parsed.identifiers:
        f.regulation = regulation
        out.extend(fetch_by_identifier(f))
    return out


# --------------------------------------------------------------------------------------
# Fusion
# --------------------------------------------------------------------------------------

SOURCE_WEIGHTS = {"identifier": 2.0, "vector": 1.0, "fulltext": 1.0}


def reciprocal_rank_fusion(lists: dict[str, list[RetrievedChunk]], k: int = RRF_K) -> list[RetrievedChunk]:
    """score = sum over sources of weight / (k + rank). Identifier hits weigh double so a
    provision the user named explicitly always outranks a mere semantic neighbour."""
    merged: dict[int, RetrievedChunk] = {}
    for source, chunks in lists.items():
        w = SOURCE_WEIGHTS.get(source, 1.0)
        for rank, c in enumerate(chunks, start=1):
            m = merged.setdefault(c.id, c)
            m.ranks[source] = rank
            m.fused_score += w / (k + rank)
            if c.vector_distance is not None:
                m.vector_distance = c.vector_distance
            if c.ts_rank is not None:
                m.ts_rank = c.ts_rank
    return sorted(merged.values(), key=lambda c: -c.fused_score)


@traceable(name="hybrid_search", run_type="retriever")
def hybrid_search(
    query: str,
    regulation: str | None = None,
    k: int = 20,
    per_source: int = 20,
) -> tuple[list[RetrievedChunk], dict[str, Any]]:
    """Vector + full-text + identifier lookups, fused with RRF. Returns (top-k, trace)."""
    parsed = parse_identifiers(query, default_regulation=regulation)
    reg = regulation or parsed.single_regulation
    lists: dict[str, list[RetrievedChunk]] = {}

    id_hits: list[RetrievedChunk] = []
    seen: set[int] = set()
    for f in parsed.identifiers:
        for c in fetch_by_identifier(f):
            if c.id not in seen:
                seen.add(c.id)
                id_hits.append(c)
    if id_hits:
        lists["identifier"] = id_hits

    lists["vector"] = vector_search(query, k=per_source, regulation=reg)
    lists["fulltext"] = fulltext_search(query, k=per_source, regulation=reg)
    fused = reciprocal_rank_fusion(lists)[:k]
    trace = {
        "query": query,
        "regulation_filter": reg,
        "identifiers": [f.label for f in parsed.identifiers],
        "identifier_hits": [c.citation for c in id_hits],
        "vector_top": [c.citation for c in lists["vector"][:5]],
        "fulltext_top": [c.citation for c in lists["fulltext"][:5]],
        "fused_top": [c.citation for c in fused[:10]],
    }
    return fused, trace
