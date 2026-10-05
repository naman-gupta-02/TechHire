"""Retrieval over job_chunks: dense, lexical, and hybrid (RRF).

- dense_search: pgvector cosine distance over bge-small embeddings (HNSW
  index). Good at paraphrase — "build data pipelines" finds "own our ETL".
- lexical_search: Postgres full-text search (tsvector + GIN). Good at exact
  tokens embeddings blur — "Rust", "Kafka", "SOC 2", company names.
  Terms are OR-ed, not AND-ed: a natural-language question has too many
  words for every one of them to appear in one chunk. Ranked with ts_rank
  (term frequency), not ts_rank_cd (cover density / term proximity): on
  long OR queries ts_rank_cd was 17x slower (p50 235 ms vs 14 ms) and
  much worse (MRR 0.37 vs 0.58) on the eval set — proximity is noise when
  the "query" is a dozen loosely related words.
- hybrid_search: Reciprocal Rank Fusion of both lists. RRF uses only ranks,
  not scores, so it needs no calibration between a cosine similarity and a
  ts_rank value that live on unrelated scales.

scripts/eval_rag.py measures all three against the same eval set.
"""
from dataclasses import dataclass, asdict

import numpy as np
from sqlalchemy import text

from rag.embeddings import Embedder, get_embedder

RRF_K = 60           # standard constant from the RRF paper (Cormack et al. 2009)
CANDIDATES = 50      # per-retriever candidate pool fed into fusion
# HNSW candidate-list size at query time (pgvector default: 40). Measured
# on the eval set at ~6k chunks: ef=100 lost 4 points of Hit@1/MRR against
# exact search; ef=400 matched exact exactly, at ~20 ms vs ~1 ms. Trivial
# next to a ~2 s LLM call, and unlike forcing an exact scan it stays
# sublinear as the corpus grows.
HNSW_EF_SEARCH = 400
RANK_FN = "ts_rank"  # see module docstring — ts_rank_cd measured worse


@dataclass
class Hit:
    chunk_id: int
    job_id: int
    section: str
    body: str
    score: float
    title: str = ""
    company: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


_HIT_COLUMNS = """
    c.id AS chunk_id, c.job_id, c.section, c.body,
    j.title, j.company, j.url
"""


def _rows_to_hits(rows) -> list[Hit]:
    return [Hit(chunk_id=r.chunk_id, job_id=r.job_id, section=r.section, body=r.body,
                score=float(r.score), title=r.title, company=r.company, url=r.url)
            for r in rows]


def _vec_literal(v: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


def dense_search(session, query: str, k: int = 10, embedder: Embedder | None = None) -> list[Hit]:
    qvec = (embedder or get_embedder()).embed_query(query)
    # SET LOCAL scopes the setting to this transaction only.
    session.execute(text(f"SET LOCAL hnsw.ef_search = {int(HNSW_EF_SEARCH)}"))
    rows = session.execute(text(f"""
        SELECT {_HIT_COLUMNS}, 1 - (c.embedding <=> CAST(:q AS vector)) AS score
        FROM job_chunks c JOIN job_listings j ON j.id = c.job_id
        ORDER BY c.embedding <=> CAST(:q AS vector)
        LIMIT :k
    """), {"q": _vec_literal(qvec), "k": k}).all()
    return _rows_to_hits(rows)


def lexical_search(session, query: str, k: int = 10) -> list[Hit]:
    # to_tsvector() stems the query and drops stopwords; re-joining its
    # lexemes with '|' turns the question into an OR query.
    rows = session.execute(text(f"""
        WITH q AS (
            SELECT to_tsquery('english', string_agg(quote_literal(lexeme), ' | ')) AS tsq
            FROM unnest(tsvector_to_array(to_tsvector('english', :q))) AS lexeme
        )
        SELECT {_HIT_COLUMNS}, {RANK_FN}(c.tsv, q.tsq) AS score
        FROM job_chunks c JOIN job_listings j ON j.id = c.job_id, q
        WHERE q.tsq IS NOT NULL AND c.tsv @@ q.tsq
        ORDER BY score DESC, c.id
        LIMIT :k
    """), {"q": query, "k": k}).all()
    return _rows_to_hits(rows)


def rrf_fuse(ranked_lists: list[list[Hit]], k: int = RRF_K) -> list[Hit]:
    """score(chunk) = Σ over lists of 1 / (k + rank). A chunk ranked well by
    both retrievers beats one ranked first by only one of them."""
    fused: dict[int, float] = {}
    first_seen: dict[int, Hit] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits, start=1):
            fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(hit.chunk_id, hit)
    out = []
    for chunk_id, score in sorted(fused.items(), key=lambda kv: -kv[1]):
        hit = first_seen[chunk_id]
        out.append(Hit(**{**hit.to_dict(), "score": score}))
    return out


def hybrid_search(session, query: str, k: int = 10, embedder: Embedder | None = None) -> list[Hit]:
    dense = dense_search(session, query, CANDIDATES, embedder)
    lexical = lexical_search(session, query, CANDIDATES)
    return rrf_fuse([dense, lexical])[:k]


SEARCHERS = {
    "dense": lambda s, q, k, e=None: dense_search(s, q, k, e),
    "lexical": lambda s, q, k, e=None: lexical_search(s, q, k),
    "hybrid": lambda s, q, k, e=None: hybrid_search(s, q, k, e),
}


def diversify(hits: list[Hit], per_job: int = 2, k: int = 8) -> list[Hit]:
    """Cap chunks per job so one long posting can't fill the whole context
    window, and drop exact-duplicate passages (identical text reposted for
    several locations)."""
    counts: dict[int, int] = {}
    seen_bodies: set[str] = set()
    out = []
    for h in hits:
        if counts.get(h.job_id, 0) >= per_job or h.body in seen_bodies:
            continue
        counts[h.job_id] = counts.get(h.job_id, 0) + 1
        seen_bodies.add(h.body)
        out.append(h)
        if len(out) == k:
            break
    return out


def similar_jobs(session, job_id: int, k: int = 6, same_company: bool = False) -> list[dict]:
    """Nearest job vectors (see rag/indexer.job_vector). Collapses reposts —
    the same title at the same company is usually one role listed in
    several cities, and five copies of it isn't five recommendations.

    Other companies only by default: every chunk's contextual header names
    the company, so same-company postings are always the nearest vectors —
    and "the same role elsewhere" is the more useful recommendation."""
    # The source vector is a scalar subquery (evaluated once, as a plan
    # parameter) rather than a join column, so the planner can drive the
    # ORDER BY from the HNSW index instead of computing every distance.
    #
    # But HNSW + a WHERE filter is a trap: the index hands back its
    # ef_search nearest vectors and the filter runs *afterwards*. For a
    # company with many postings, all ~40 nearest are that company, the
    # "other companies" filter removes every one, and the result is empty.
    # pgvector >= 0.8 iterative scans keep pulling from the index until
    # enough rows survive the filter; relaxed_order may return them slightly
    # out of distance order, so results are re-sorted below.
    session.execute(text(f"SET LOCAL hnsw.ef_search = {int(HNSW_EF_SEARCH)}"))
    session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    rows = session.execute(text("""
        SELECT j.id, j.title, j.company, j.city, j.state, j.work_mode,
               j.experience_level, j.url,
               1 - (v.embedding <=> (SELECT embedding FROM job_vectors WHERE job_id = :id)) AS similarity
        FROM job_vectors v
        JOIN job_listings j ON j.id = v.job_id
        WHERE v.job_id <> :id
          AND (:same_company OR j.company <> (SELECT company FROM job_listings WHERE id = :id))
        ORDER BY v.embedding <=> (SELECT embedding FROM job_vectors WHERE job_id = :id)
        LIMIT :pool
    """), {"id": job_id, "pool": k * 5, "same_company": same_company}).all()
    src = session.execute(text("SELECT lower(title) AS title_l, company FROM job_listings WHERE id = :id"),
                          {"id": job_id}).first()
    out, seen = [], {(src.title_l, src.company)} if src else set()
    for r in sorted(rows, key=lambda r: -r.similarity):
        key = (r.title.lower(), r.company)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": r.id, "title": r.title, "company": r.company,
            "location": ", ".join(x for x in [r.city, r.state] if x) or None,
            "work_mode": r.work_mode, "experience_level": r.experience_level,
            "url": r.url, "similarity": round(float(r.similarity), 3),
        })
        if len(out) == k:
            break
    return out
