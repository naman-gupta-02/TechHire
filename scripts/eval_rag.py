"""Evaluate TechHire's RAG pipeline.

    python scripts/eval_rag.py build              # (re)generate eval/rag_eval_set.json
    python scripts/eval_rag.py retrieval          # dense vs lexical vs hybrid
    python scripts/eval_rag.py ablation           # chunking strategies (dense, in-memory)
    python scripts/eval_rag.py answers --n 15     # end-to-end through the answer graph

Eval set
--------
Built from the corpus itself, then frozen in eval/rag_eval_set.json so every
run scores the same questions:

- answerable: sample real postings (<= MAX_PER_COMPANY per company, so the
  ~190 OpenAI and ~190 Palantir postings don't dominate), pick one of each
  posting's chunks, and have an LLM write the question a job seeker would
  type that the passage answers — without naming the company or the exact
  title, and paraphrasing rather than copying distinctive phrases.
  Gold = that posting, plus any repost of it (same title + company, usually
  another city): retrieving the Seattle copy of the role isn't a miss.
- unanswerable: hand-written questions about jobs the corpus doesn't have
  (nursing, trucking, ...). The answer graph should abstain on all of them.

Known bias: questions come from a single passage, so they're narrower than
real queries, and the generator may echo the passage's wording (which
flatters lexical search). Treat the numbers as a relative comparison
between configurations, not absolute production quality.

Metrics (job level — results are collapsed to unique jobs in rank order)
  Hit@k  fraction of questions with a gold job in the top k
  MRR@10 mean of 1/rank of the first gold job (0 if not in top 10)
"""
import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

load_dotenv()

from db.session import SessionLocal  # noqa: E402
from db.models import JobChunk, JobListing  # noqa: E402

EVAL_PATH = Path(__file__).resolve().parent.parent / "eval" / "rag_eval_set.json"
RESULTS_PATH = EVAL_PATH.with_name("rag_eval_results.json")
GEN_MODEL = "openai/gpt-oss-20b"
N_ANSWERABLE = 80
MAX_PER_COMPANY = 4
SEED = 7
KS = (1, 5, 10)

UNANSWERABLE = [
    "Are there any underwater welding jobs in Antarctica?",
    "Which hospitals are hiring registered nurses for night shifts?",
    "Find me CDL truck driving jobs with sign-on bonuses.",
    "Any pastry chef openings at French restaurants?",
    "Which schools are hiring high school math teachers?",
    "What real estate agent roles offer a commission split above 70%?",
    "Are airlines hiring first officers with 1,500 flight hours?",
    "Which veterinary clinics need a vet tech on weekends?",
    "Warehouse forklift operator jobs paying over $25 an hour?",
    "Dental hygienist positions that offer a four-day work week?",
]

QUESTION_PROMPT = """Here is a passage from a job posting ({section} section of a "{title}" role).

PASSAGE:
{body}

Write ONE question that a job seeker might type into a job-search assistant, which this passage would help answer.
Rules:
- Do NOT mention the company name ({company}) or the exact job title.
- Paraphrase: don't copy distinctive phrases from the passage.
- Make it specific enough that this kind of role is what they're looking for, like a real search.
- Output only the question."""


# ── build ────────────────────────────────────────────────────────────────────

async def _generate_question(llm, chunk, job) -> str:
    prompt = QUESTION_PROMPT.format(section=chunk.section, title=job.title,
                                    company=job.company, body=chunk.body[:1500])
    for attempt in range(5):
        try:
            q = await llm(GEN_MODEL, [{"role": "user", "content": prompt}], 120, 0.7)
            q = q.strip().strip('"').splitlines()[0].strip()
            if q:
                return q
        except Exception as e:
            print(f"    retry ({type(e).__name__}), sleeping 15s")
            await asyncio.sleep(15)
    raise RuntimeError("question generation kept failing")


def build(args):
    from ai.llm import configured_groq_key, make_groq_llm
    llm = make_groq_llm(configured_groq_key())
    rng = random.Random(SEED)

    with SessionLocal() as s:
        indexed = s.scalars(select(JobListing).where(
            JobListing.id.in_(select(JobChunk.job_id).distinct()))).all()
        rng.shuffle(indexed)
        per_company: dict[str, int] = {}
        picked = []
        for job in indexed:
            if per_company.get(job.company, 0) >= MAX_PER_COMPANY:
                continue
            chunks = s.scalars(select(JobChunk).where(
                JobChunk.job_id == job.id, JobChunk.section != "Profile",
                text("array_length(regexp_split_to_array(body, '\\s+'), 1) >= 40"))).all()
            if not chunks:
                continue
            per_company[job.company] = per_company.get(job.company, 0) + 1
            picked.append((job, rng.choice(chunks)))
            if len(picked) == N_ANSWERABLE:
                break

        items = []
        for i, (job, chunk) in enumerate(picked, start=1):
            question = asyncio.run(_generate_question(llm, chunk, job))
            gold = s.scalars(select(JobListing.id).where(
                text("lower(title) = lower(:t)"), JobListing.company == job.company,
                JobListing.id.in_(select(JobChunk.job_id).distinct())).params(t=job.title)).all()
            items.append({
                "id": f"a{i:03d}", "answerable": True, "question": question,
                "job_id": job.id, "chunk_id": chunk.id, "gold_job_ids": sorted(gold),
                "company": job.company, "title": job.title, "section": chunk.section,
            })
            print(f"  [{i}/{len(picked)}] {job.company:>12} | {question}")
            time.sleep(1.5)  # stay under Groq's free-tier tokens-per-minute cap

    items += [{"id": f"u{i:03d}", "answerable": False, "question": q}
              for i, q in enumerate(UNANSWERABLE, start=1)]
    EVAL_PATH.parent.mkdir(exist_ok=True)
    EVAL_PATH.write_text(json.dumps({"seed": SEED, "generator": GEN_MODEL, "items": items}, indent=2))
    print(f"\nWrote {len(items)} items to {EVAL_PATH}")


# ── scoring ──────────────────────────────────────────────────────────────────

def _unique_jobs(job_ids) -> list[int]:
    out = []
    for j in job_ids:
        if j not in out:
            out.append(j)
    return out


def score(ranked_job_ids: list[int], gold: set[int]) -> dict:
    ranked = _unique_jobs(ranked_job_ids)
    first = next((i for i, j in enumerate(ranked[:10], start=1) if j in gold), None)
    out = {f"hit@{k}": float(first is not None and first <= k) for k in KS}
    out["mrr@10"] = 1.0 / first if first else 0.0
    return out


def _aggregate(rows: list[dict]) -> dict:
    return {k: round(statistics.mean(r[k] for r in rows), 3) for k in rows[0]}


def _load_items(answerable=True):
    items = json.loads(EVAL_PATH.read_text())["items"]
    return [i for i in items if i["answerable"] == answerable]


def _print_table(title: str, results: dict):
    cols = [f"hit@{k}" for k in KS] + ["mrr@10"]
    extra = [c for c in next(iter(results.values())) if c not in cols]
    print(f"\n{title}\n")
    print("| config | " + " | ".join(cols + extra) + " |")
    print("|---" * (1 + len(cols) + len(extra)) + "|")
    for name, agg in results.items():
        print(f"| {name} | " + " | ".join(str(agg[c]) for c in cols + extra) + " |")


def _save(section: str, payload):
    data = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else {}
    data[section] = payload
    RESULTS_PATH.write_text(json.dumps(data, indent=2))


# ── retrieval: dense vs lexical vs hybrid ────────────────────────────────────

def retrieval(args):
    from rag.embeddings import get_embedder
    from rag.retrieval import SEARCHERS
    items = _load_items()
    embedder = get_embedder()
    embedder.embed_query("warm up")  # keep model load out of the latency numbers

    results, misses = {}, {}
    with SessionLocal() as s:
        for mode, search in SEARCHERS.items():
            rows, latencies = [], []
            for it in items:
                t0 = time.perf_counter()
                hits = search(s, it["question"], 30, embedder)
                latencies.append((time.perf_counter() - t0) * 1000)
                rows.append(score([h.job_id for h in hits], set(it["gold_job_ids"])))
                if rows[-1]["hit@10"] == 0:
                    misses.setdefault(mode, []).append(it["id"])
                s.rollback()  # end the transaction SET LOCAL ran in
            agg = _aggregate(rows)
            agg["p50 ms"] = round(statistics.median(latencies), 1)
            results[mode] = agg

    _print_table(f"Retrieval — {len(items)} answerable questions, job-level", results)
    for mode, ids in misses.items():
        print(f"  {mode} misses@10: {len(ids)}")
    _save("retrieval", {"n": len(items), "results": results, "misses@10": misses})


# ── ablation: chunking strategies ────────────────────────────────────────────

def _fixed_windows(job, size=200, overlap=40) -> list[str]:
    words = f"{job.title} at {job.company}. {job.description or ''}".split()
    step = size - overlap
    return [" ".join(words[i:i + size]) for i in range(0, max(len(words) - overlap, 1), step)]


def ablation(args):
    """Dense retrieval over in-memory indexes built with each strategy.
    Same embedder, same questions, exact cosine search — only the chunking
    differs. Production (sections-v1) is re-embedded here too, rather than
    read from pgvector, so every strategy goes through the identical path."""
    import numpy as np
    from rag.chunking import chunk_job, find_template_paragraphs
    from rag.embeddings import get_embedder

    items = _load_items()
    embedder = get_embedder()
    with SessionLocal() as s:
        jobs = s.scalars(select(JobListing).where(
            JobListing.id.in_(select(JobChunk.job_id).distinct()))).all()
    template = find_template_paragraphs(j.description for j in jobs)

    strategies = {
        "sections + headers (prod)": lambda j: [c.content for c in chunk_job(j, template)],
        "sections, no headers": lambda j: [c.body for c in chunk_job(j, template)],
        "fixed 200w windows": _fixed_windows,
        "whole posting (1 vector)": lambda j: [f"{j.title} at {j.company}. {j.description or ''}"],
    }
    qvecs = np.stack([embedder.embed_query(it["question"]) for it in items])

    results = {}
    for name, fn in strategies.items():
        texts, owners = [], []
        for j in jobs:
            for t in fn(j):
                texts.append(t)
                owners.append(j.id)
        t0 = time.perf_counter()
        mat = embedder.embed_passages(texts)
        print(f"  {name}: {len(texts)} chunks embedded in {time.perf_counter() - t0:.0f}s")
        owners = np.array(owners)
        sims = qvecs @ mat.T
        rows = []
        for qi, it in enumerate(items):
            top = np.argsort(-sims[qi])[:200]
            rows.append(score(owners[top].tolist(), set(it["gold_job_ids"])))
        agg = _aggregate(rows)
        agg["chunks"] = len(texts)
        results[name] = agg

    _print_table(f"Chunking ablation — dense retrieval, {len(items)} questions, job-level", results)
    _save("ablation", {"n": len(items), "results": results})


# ── answers: end-to-end through the LangGraph answer graph ───────────────────

def answers(args):
    import api  # reuse the exact production retriever + graph wiring
    from ai.llm import configured_groq_key, make_groq_llm
    from ai.answer_graph import build_answer_graph

    graph = build_answer_graph(make_groq_llm(configured_groq_key()), api._rag_retrieve)
    rng = random.Random(SEED)
    answerable = _load_items()
    sample = rng.sample(answerable, min(args.n, len(answerable))) + _load_items(answerable=False)

    rows = []
    for i, it in enumerate(sample, start=1):
        for attempt in range(4):
            state = asyncio.run(graph.ainvoke({"question": it["question"]}))
            if state["status"] != "error":
                break
            print("    rate-limited, sleeping 30s")
            time.sleep(30)
        cited_jobs = {state["sources"][n - 1]["job_id"] for n in state.get("cited", [])}
        row = {"id": it["id"], "answerable": it["answerable"], "status": state["status"],
               "attempts": state.get("attempts", 0)}
        if it["answerable"]:
            retrieved = {src["job_id"] for src in state["sources"]}
            row["gold_retrieved"] = bool(retrieved & set(it["gold_job_ids"]))
            row["gold_cited"] = bool(cited_jobs & set(it["gold_job_ids"]))
        rows.append(row)
        print(f"  [{i}/{len(sample)}] {row}")
        time.sleep(args.sleep)  # Groq free tier: ~8k tokens/min on the answer model

    ans = [r for r in rows if r["answerable"]]
    una = [r for r in rows if not r["answerable"]]
    pct = lambda xs: round(100 * statistics.mean(xs), 1) if xs else None  # noqa: E731
    summary = {
        "answerable_n": len(ans),
        "answered_%": pct([r["status"] == "answered" for r in ans]),
        "false_abstain_%": pct([r["status"] in ("abstained", "no_results") for r in ans]),
        "ungrounded_%": pct([r["status"] == "ungrounded" for r in ans]),
        "needed_retry_%": pct([r["attempts"] > 1 for r in ans]),
        "gold_in_context_%": pct([r["gold_retrieved"] for r in ans]),
        "gold_cited_%": pct([r["gold_cited"] for r in ans]),
        "gold_cited_when_in_context_%": pct([r["gold_cited"] for r in ans if r["gold_retrieved"]]),
        "unanswerable_n": len(una),
        "correct_abstain_%": pct([r["status"] in ("abstained", "no_results") for r in una]),
    }
    print("\nEnd-to-end answers\n")
    for k, v in summary.items():
        print(f"  {k:30} {v}")
    _save("answers", {"summary": summary, "rows": rows})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("retrieval")
    sub.add_parser("ablation")
    p = sub.add_parser("answers")
    p.add_argument("--n", type=int, default=15, help="answerable questions to sample")
    p.add_argument("--sleep", type=float, default=20, help="seconds between questions (rate limits)")
    args = parser.parse_args()
    {"build": build, "retrieval": retrieval, "ablation": ablation, "answers": answers}[args.cmd](args)


if __name__ == "__main__":
    main()
