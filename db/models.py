from datetime import datetime, timezone
from typing import Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, Boolean, Float, DateTime, Integer, ForeignKey, Computed, Index
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import mapped_column, Mapped
from .session import Base


class JobListing(Base):
    __tablename__ = "job_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Unique identifier from JSearch — prevents duplicate inserts
    source_job_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Core
    title:   Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    source:  Mapped[str] = mapped_column(String(100))   # "indeed", "lever", etc.
    url:     Mapped[str] = mapped_column(Text)

    # Timestamps
    posted_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime]           = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Location
    city:      Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    state:     Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    country:   Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    is_remote: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    work_mode: Mapped[Optional[str]]  = mapped_column(String(20), nullable=True)  # remote / hybrid / onsite

    # Role details
    job_type:         Mapped[Optional[str]]  = mapped_column(String(50), nullable=True)   # FULLTIME, INTERN, CONTRACT
    experience_level: Mapped[Optional[str]]  = mapped_column(String(20), nullable=True)   # intern / entry / mid / senior
    description:      Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    responsibilities: Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True)
    qualifications:   Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True)
    benefits:         Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True)

    # Compensation
    salary_min:      Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max:      Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[Optional[str]]   = mapped_column(String(10), nullable=True)
    salary_period:   Mapped[Optional[str]]   = mapped_column(String(20), nullable=True)  # YEAR / HOUR / MONTH

    # Skills
    required_skills: Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True)

    # International students
    visa_sponsorship: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Employment start info extracted from title/description (e.g. "Summer 2026")
    start_date_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # AI-generated summary (cached)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ── RAG index ────────────────────────────────────────────────────────────────

# Output size of BAAI/bge-small-en-v1.5 (see rag/embeddings.py). Changing the
# embedding model means changing this, dropping job_chunks/job_vectors, and
# re-running scripts/build_rag_index.py.
EMBED_DIM = 384

# HNSW over cosine distance: approximate nearest-neighbour search that stays
# fast as the table grows, unlike an exact scan. m / ef_construction are
# pgvector's defaults, spelled out so they're visible.
_HNSW = dict(
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)


class JobChunk(Base):
    """One retrievable passage of a job posting (see rag/chunking.py)."""
    __tablename__ = "job_chunks"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id:      Mapped[int] = mapped_column(ForeignKey("job_listings.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    section:     Mapped[str] = mapped_column(String(120))

    # body = the passage itself, shown to users as the citation snippet.
    # content = contextual header ("<title> at <company> — <section>") + body;
    # this is what gets embedded and full-text indexed, so a chunk that says
    # "you'll own our ingestion pipeline" still carries which job it's from.
    body:      Mapped[str] = mapped_column(Text)
    content:   Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Vector(EMBED_DIM))
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True))

    __table_args__ = (
        Index("ix_job_chunks_embedding_hnsw", "embedding", **_HNSW),
        Index("ix_job_chunks_tsv", "tsv", postgresql_using="gin"),
    )


class JobVector(Base):
    """One vector per job (mean of its chunk vectors) for "similar roles",
    plus the bookkeeping that makes re-indexing incremental."""
    __tablename__ = "job_vectors"

    job_id:    Mapped[int]  = mapped_column(ForeignKey("job_listings.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list] = mapped_column(Vector(EMBED_DIM))
    # sha256 of (chunker version, embedding model, chunk texts). A job is
    # re-embedded only when this changes — i.e. its text was re-parsed or
    # the chunking/model changed — so re-running the indexer is cheap.
    content_hash: Mapped[str] = mapped_column(String(64))
    n_chunks:     Mapped[int] = mapped_column(Integer)
    indexed_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_job_vectors_embedding_hnsw", "embedding", **_HNSW),
    )

