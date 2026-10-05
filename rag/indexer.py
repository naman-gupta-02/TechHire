"""Chunk + embed job postings into job_chunks / job_vectors.

Incremental: each job's chunks are hashed together with the chunker version
and embedding model name. Only jobs whose hash changed (new posting,
re-parsed text, different chunking or model) are re-embedded, so it's
cheap to run after every scrape.

Synthetic rows (source_job_id 'synthetic-%', from seed_synthetic_jobs.py)
are skipped by default: they exist for load testing, and their templated
filler text would crowd real postings out of retrieval results.
"""
import hashlib
import time

import numpy as np
from sqlalchemy import select, delete

from db.models import JobListing, JobChunk, JobVector
from rag.chunking import CHUNKER_VERSION, chunk_job, find_template_paragraphs
from rag.embeddings import Embedder, get_embedder

JOBS_PER_BATCH = 32


def _content_hash(model_name: str, contents: list[str]) -> str:
    h = hashlib.sha256(f"{CHUNKER_VERSION}\0{model_name}".encode())
    for c in contents:
        h.update(b"\0" + c.encode())
    return h.hexdigest()


def job_vector(chunk_vecs: np.ndarray) -> np.ndarray:
    """A job's vector is the re-normalized mean of its chunk vectors — the
    centroid of everything the posting says, used for "similar roles"."""
    v = chunk_vecs.mean(axis=0)
    return v / (np.linalg.norm(v) or 1.0)


def index_jobs(session, embedder: Embedder | None = None, include_synthetic: bool = False,
               force: bool = False, log=print) -> dict:
    embedder = embedder or get_embedder()

    stmt = select(JobListing)
    if not include_synthetic:
        stmt = stmt.where(~JobListing.source_job_id.like("synthetic-%"))
    jobs = session.scalars(stmt).all()

    # Template detection needs the whole corpus, not just the stale jobs:
    # whether a paragraph is template text depends on how many postings
    # contain it. If a new posting tips a paragraph over the threshold, the
    # jobs containing it get new chunk hashes and are re-indexed below.
    template = find_template_paragraphs(j.description for j in jobs)

    existing = dict(session.execute(select(JobVector.job_id, JobVector.content_hash)).all())
    pending = []
    for job in jobs:
        chunks = chunk_job(job, template)
        digest = _content_hash(embedder.model_name, [c.content for c in chunks])
        if force or existing.get(job.id) != digest:
            pending.append((job, chunks, digest))

    log(f"RAG index: {len(jobs)} jobs, {len(pending)} new or changed, "
        f"{len(jobs) - len(pending)} up to date")

    t0 = time.perf_counter()
    n_chunks = 0
    for i in range(0, len(pending), JOBS_PER_BATCH):
        batch = pending[i:i + JOBS_PER_BATCH]
        contents = [c.content for _, chunks, _ in batch for c in chunks]
        vecs = embedder.embed_passages(contents)

        ids = [job.id for job, _, _ in batch]
        session.execute(delete(JobChunk).where(JobChunk.job_id.in_(ids)))
        offset = 0
        for job, chunks, digest in batch:
            job_vecs = vecs[offset:offset + len(chunks)]
            offset += len(chunks)
            session.add_all(
                JobChunk(job_id=job.id, chunk_index=c.index, section=c.section,
                         body=c.body, content=c.content, embedding=v)
                for c, v in zip(chunks, job_vecs)
            )
            session.merge(JobVector(job_id=job.id, embedding=job_vector(job_vecs),
                                    content_hash=digest, n_chunks=len(chunks)))
        # Commit per batch so an interrupted run keeps its progress.
        session.commit()
        n_chunks += len(contents)
        log(f"  embedded {min(i + JOBS_PER_BATCH, len(pending))}/{len(pending)} jobs "
            f"({n_chunks} chunks, {time.perf_counter() - t0:.0f}s)")

    return {"jobs": len(jobs), "indexed": len(pending), "chunks": n_chunks,
            "seconds": round(time.perf_counter() - t0, 1)}
