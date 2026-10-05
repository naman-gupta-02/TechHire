"""Indexing + retrieval against the real pgvector schema, with a
deterministic fake embedder (bag of hashed words) — so CI doesn't download
a model, and "similar" is predictable from word overlap."""
import hashlib
import re

import numpy as np
import pytest
from sqlalchemy import func, select

from db.models import EMBED_DIM, JobChunk, JobListing, JobVector
from rag.indexer import index_jobs
from rag.retrieval import Hit, dense_search, hybrid_search, lexical_search, rrf_fuse, similar_jobs
from tests.conftest import make_job


class FakeEmbedder:
    model_name = "fake-bow"

    def _vec(self, text):
        v = np.zeros(EMBED_DIM, dtype=np.float32)
        for w in re.findall(r"[a-z]+", text.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % EMBED_DIM] += 1
        return v / (np.linalg.norm(v) or 1.0)

    def embed_passages(self, texts):
        return np.stack([self._vec(t) for t in texts])

    def embed_query(self, text):
        return self._vec(text)


EMB = FakeEmbedder()


def para(*words, n=40):
    return " ".join((list(words) * n)[:n]) + "."


def seed(session):
    k8s = make_job(session, source_job_id="r-k8s", title="Platform Engineer", company="Acme",
                   description=f"The role\n\n{para('kubernetes', 'operators', 'golang', 'clusters')}")
    ml = make_job(session, source_job_id="r-ml", title="ML Engineer", company="Beta",
                  description=f"The role\n\n{para('fraud', 'models', 'pytorch', 'underwriting')}")
    ml2 = make_job(session, source_job_id="r-ml2", title="Risk ML Engineer", company="Gamma",
                   description=f"The role\n\n{para('fraud', 'models', 'pytorch', 'risk')}")
    ml_same_co = make_job(session, source_job_id="r-ml3", title="Fraud Scientist", company="Beta",
                          description=f"The role\n\n{para('fraud', 'models', 'pytorch', 'statistics')}")
    synthetic = make_job(session, source_job_id="synthetic-1", title="Filler", company="Acme",
                         description=para("kubernetes"))
    return k8s, ml, ml2, ml_same_co, synthetic


@pytest.fixture()
def indexed(db_session):
    jobs = seed(db_session)
    result = index_jobs(db_session, embedder=EMB, log=lambda *_: None)
    return jobs, result


def test_indexes_real_jobs_and_skips_synthetic(db_session, indexed):
    (k8s, ml, ml2, ml_same_co, synthetic), result = indexed
    assert result["indexed"] == 4
    ids = set(db_session.scalars(select(JobVector.job_id)))
    assert synthetic.id not in ids and k8s.id in ids


def test_reindex_is_incremental(db_session, indexed):
    (k8s, *_), _ = indexed
    assert index_jobs(db_session, embedder=EMB, log=lambda *_: None)["indexed"] == 0

    k8s.description = f"The role\n\n{para('kubernetes', 'operators', 'terraform')}"
    db_session.commit()
    assert index_jobs(db_session, embedder=EMB, log=lambda *_: None)["indexed"] == 1


def test_changing_the_embedding_model_reindexes_everything(db_session, indexed):
    class OtherModel(FakeEmbedder):
        model_name = "fake-bow-v2"
    assert index_jobs(db_session, embedder=OtherModel(), log=lambda *_: None)["indexed"] == 4


@pytest.mark.parametrize("search", ["dense", "lexical", "hybrid"])
def test_each_retriever_finds_the_matching_job(db_session, indexed, search):
    (k8s, *_), _ = indexed
    fn = {
        "dense": lambda q: dense_search(db_session, q, 3, EMB),
        "lexical": lambda q: lexical_search(db_session, q, 3),
        "hybrid": lambda q: hybrid_search(db_session, q, 3, EMB),
    }[search]
    hits = fn("golang kubernetes operators")
    assert hits and hits[0].job_id == k8s.id
    assert hits[0].title == "Platform Engineer" and hits[0].company == "Acme"


def test_similar_jobs_prefers_other_companies_by_default(db_session, indexed):
    (k8s, ml, ml2, ml_same_co, _), _ = indexed
    other = similar_jobs(db_session, ml.id, k=3)
    assert other[0]["id"] == ml2.id
    assert all(r["company"] != "Beta" for r in other)

    with_same = [r["id"] for r in similar_jobs(db_session, ml.id, k=3, same_company=True)]
    assert ml_same_co.id in with_same


def test_similar_jobs_collapses_reposts(db_session, indexed):
    (k8s, ml, ml2, *_), _ = indexed
    make_job(db_session, source_job_id="r-ml2-nyc", title="Risk ML Engineer", company="Gamma",
             description=f"The role\n\n{para('fraud', 'models', 'pytorch', 'risk')}")
    index_jobs(db_session, embedder=EMB, log=lambda *_: None)
    titles = [(r["title"], r["company"]) for r in similar_jobs(db_session, ml.id, k=5)]
    assert titles.count(("Risk ML Engineer", "Gamma")) == 1


def test_deleting_a_job_cascades_to_its_chunks(db_session, indexed):
    (k8s, *_), _ = indexed
    db_session.delete(db_session.get(JobListing, k8s.id))
    db_session.commit()
    n = db_session.scalar(select(func.count()).select_from(JobChunk).where(JobChunk.job_id == k8s.id))
    assert n == 0


def test_rrf_rewards_agreement_between_retrievers():
    def hits(*ids):
        return [Hit(chunk_id=i, job_id=i, section="", body="", score=0) for i in ids]
    # 2 is only 2nd in both lists, but beats 1 and 3, which each top one list and miss the other.
    fused = rrf_fuse([hits(1, 2), hits(3, 2)])
    assert fused[0].chunk_id == 2
