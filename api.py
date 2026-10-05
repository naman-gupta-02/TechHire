import os
import asyncio
import json as json_lib
import re as re_module
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional
from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, and_, func, text
from dotenv import load_dotenv
from db.session import init_db, SessionLocal
from db.models import JobListing, JobVector
from scraper.runner import refresh as run_refresh
from core.redis_client import get_redis
from core.cache import jobs_cache_key, cache_get, cache_set, cache_clear_prefix
from core.ratelimit import get_client_ip, rate_limit, cooldown
from ai.llm import configured_groq_key, reasoning_kwargs, make_groq_llm
from ai.summary_graph import build_summary_graph
from ai.answer_graph import build_answer_graph
from rag.retrieval import SEARCHERS, diversify, hybrid_search, similar_jobs

load_dotenv()

app = FastAPI(title="TechHire API")

_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
JOBS_CACHE_TTL = 45  # seconds


@app.on_event("startup")
def startup():
    init_db()


def _job_to_dict(j: JobListing, full: bool = False) -> dict:
    """`full=False` (used by the list endpoint) omits the heavy free-text
    fields — description/responsibilities/qualifications/benefits can run
    several KB per row and aren't rendered in the list view, so shipping
    them on every /jobs page multiplies payload size for no UI benefit.
    The detail endpoint (`full=True`) still returns everything."""
    d = {
        "id": j.id,
        "source_job_id": j.source_job_id,
        "title": j.title,
        "company": j.company,
        "source": j.source,
        "url": j.url,
        "posted_at": j.posted_at.isoformat() if j.posted_at else None,
        "expires_at": j.expires_at.isoformat() if j.expires_at else None,
        "city": j.city,
        "state": j.state,
        "country": j.country,
        "is_remote": j.is_remote,
        "work_mode": j.work_mode,
        "job_type": j.job_type,
        "experience_level": j.experience_level,
        "required_skills": j.required_skills or [],
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "salary_currency": j.salary_currency,
        "salary_period": j.salary_period,
        "visa_sponsorship": j.visa_sponsorship,
        "start_date_text": j.start_date_text,
    }
    if full:
        d["description"] = j.description
        d["responsibilities"] = j.responsibilities or []
        d["qualifications"] = j.qualifications or []
        d["benefits"] = j.benefits or []
    return d


def _build_query(
    search, skills, visa_only, salary_min, salary_max,
    work_modes, experience_levels, date_posted, seasons
):
    stmt = select(JobListing)

    if search.strip():
        q = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(JobListing.title).like(q),
                func.lower(JobListing.company).like(q),
            )
        )

    if skills:
        for skill in skills:
            # Uses the same IMMUTABLE wrapper the trigram index in
            # db/session.py is built on, so this stays index-backed —
            # the built-in array_to_string() can't be indexed directly.
            stmt = stmt.where(
                func.immutable_array_to_string(JobListing.required_skills, ",").ilike(
                    f"%{skill.lower()}%"
                )
            )

    if visa_only:
        stmt = stmt.where(JobListing.visa_sponsorship == True)

    if salary_min > 0:
        stmt = stmt.where(
            and_(
                JobListing.salary_min.isnot(None),
                JobListing.salary_min >= salary_min,
            )
        )

    if salary_max < 300000:
        stmt = stmt.where(
            or_(
                JobListing.salary_max.is_(None),
                JobListing.salary_max <= salary_max,
            )
        )

    if work_modes:
        stmt = stmt.where(JobListing.work_mode.in_(work_modes))

    if experience_levels:
        stmt = stmt.where(JobListing.experience_level.in_(experience_levels))

    if date_posted != "any":
        days = {"24h": 1, "7d": 7, "30d": 30}.get(date_posted, 30)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(JobListing.posted_at >= cutoff)

    if seasons:
        stmt = stmt.where(
            or_(*[func.lower(JobListing.start_date_text).contains(s.lower()) for s in seasons])
        )

    return stmt


@app.get("/jobs")
def get_jobs(
    search: str = Query(default=""),
    skills: list[str] = Query(default=[]),
    visa_only: bool = Query(default=False),
    salary_min: int = Query(default=0),
    salary_max: int = Query(default=300000),
    work_modes: list[str] = Query(default=[]),
    experience_levels: list[str] = Query(default=[]),
    date_posted: str = Query(default="any"),
    seasons: list[str] = Query(default=[]),
    sort: str = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    r = get_redis()
    cache_key = jobs_cache_key({
        "search": search, "skills": skills, "visa_only": visa_only,
        "salary_min": salary_min, "salary_max": salary_max,
        "work_modes": work_modes, "experience_levels": experience_levels,
        "date_posted": date_posted, "seasons": seasons, "sort": sort,
        "page": page, "page_size": page_size,
    })
    cached = cache_get(r, cache_key)
    if cached is not None:
        return cached

    with SessionLocal() as session:
        stmt = _build_query(
            search, skills, visa_only, salary_min, salary_max,
            work_modes, experience_levels, date_posted, seasons,
        )

        # Count total matching rows
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = session.scalar(count_stmt)

        # Apply sort
        if sort == "salary":
            stmt = stmt.order_by(
                JobListing.salary_max.desc().nullslast(),
                JobListing.salary_min.desc().nullslast(),
                JobListing.id.desc(),
            )
        else:
            stmt = stmt.order_by(
                JobListing.posted_at.desc().nullslast(),
                JobListing.id.desc(),
            )

        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        jobs = session.scalars(stmt).all()

        result = {
            "jobs": [_job_to_dict(j) for j in jobs],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, -(-total // page_size)),  # ceiling division
        }
        cache_set(r, cache_key, result, JOBS_CACHE_TTL)
        return result


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    with SessionLocal() as session:
        j = session.get(JobListing, job_id)
        if not j:
            raise HTTPException(status_code=404, detail="Job not found")
        return _job_to_dict(j, full=True)


# ── Refresh (incremental scrape) ────────────────────────────────────────────

_scrape_state = {
    "status": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}
_scrape_lock = asyncio.Lock()


async def _run_scrape_job():
    _scrape_state.update(
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        error=None,
    )
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_refresh)
        _scrape_state.update(
            status="done",
            result=result,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        cache_clear_prefix(get_redis(), "jobs:")
    except Exception as e:
        _scrape_state.update(
            status="error",
            error=str(e),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    finally:
        if _scrape_lock.locked():
            _scrape_lock.release()


@app.post("/scrape/refresh")
async def trigger_refresh(x_admin_key: str = Header(default="")):
    if ADMIN_API_KEY and x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Admin key required for this action")

    if _scrape_lock.locked():
        return {"status": "already_running"}

    allowed, retry_after = cooldown(get_redis(), "cooldown:scrape-refresh", 900)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Refresh was triggered recently — try again in {retry_after}s",
        )

    await _scrape_lock.acquire()
    asyncio.create_task(_run_scrape_job())
    return {"status": "started"}


@app.get("/scrape/status")
def scrape_status():
    return _scrape_state


# ── AI summary ────────────────────────────────────────────────────────────────

def _build_job_context(j: JobListing) -> str:
    parts = [
        f"Job Title: {j.title}",
        f"Company: {j.company}",
        f"Work Mode: {j.work_mode or 'remote'}",
        f"Experience Level: {j.experience_level or 'not specified'}",
        f"Job Type: {j.job_type or 'Full-time'}",
    ]
    if j.salary_min or j.salary_max:
        lo = f"${int(j.salary_min):,}" if j.salary_min else "?"
        hi = f"${int(j.salary_max):,}" if j.salary_max else "?"
        parts.append(f"Salary: {lo} – {hi} / {j.salary_period or 'yr'}")
    if j.visa_sponsorship is True:
        parts.append("Visa Sponsorship: Yes")
    elif j.visa_sponsorship is False:
        parts.append("Visa Sponsorship: No")
    if j.required_skills:
        parts.append(f"Key Skills: {', '.join(j.required_skills[:12])}")
    if j.city or j.state:
        loc = ", ".join(x for x in [j.city, j.state] if x)
        parts.append(f"Location: {loc}")
    parts.append(f"\nFull Job Description:\n{(j.description or '')[:3000]}")
    return "\n".join(parts)


@lru_cache(maxsize=1)
def _summary_graph(api_key: str):
    return build_summary_graph(make_groq_llm(api_key))


@app.get("/jobs/{job_id}/summary")
async def get_job_summary(job_id: int, refresh: bool = False):
    api_key = configured_groq_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY not configured. Add it to your .env file. Get a free key at console.groq.com"
        )

    with SessionLocal() as session:
        j = session.get(JobListing, job_id)
        if not j:
            raise HTTPException(status_code=404, detail="Job not found")

        if j.ai_summary and not refresh:
            return {"summary": j.ai_summary, "cached": True}

        if not j.description:
            raise HTTPException(status_code=422, detail="No description to summarize")

        # 3 models in parallel → synthesis, degrading gracefully if some of
        # them fail — see ai/summary_graph.py.
        result = await _summary_graph(api_key).ainvoke({"context": _build_job_context(j)})
        if result["strategy"] == "failed":
            raise HTTPException(status_code=502, detail=f"All summary models failed — {result['error']}")

        # Cache in DB
        session.execute(
            text("UPDATE job_listings SET ai_summary = :s WHERE id = :id"),
            {"s": result["summary"], "id": job_id}
        )
        session.commit()

        return {
            "summary": result["summary"],
            "cached": False,
            "strategy": result["strategy"],
            "drafts": [
                {"model": d["model"], "ok": d["text"] is not None, "seconds": d["seconds"], "error": d["error"]}
                for d in result["drafts"]
            ],
        }


# ── RAG: similar roles, search, grounded Q&A ────────────────────────────────

RAG_CANDIDATES = 30       # fused hybrid hits considered...
RAG_CONTEXT_CHUNKS = 8    # ...of which at most this many reach the LLM


def _rag_retrieve(question: str) -> list[dict]:
    with SessionLocal() as session:
        hits = hybrid_search(session, question, k=RAG_CANDIDATES)
    return [h.to_dict() for h in diversify(hits, per_job=2, k=RAG_CONTEXT_CHUNKS)]


@lru_cache(maxsize=1)
def _answer_graph(api_key: str):
    return build_answer_graph(make_groq_llm(api_key), _rag_retrieve)


@app.get("/jobs/{job_id}/similar")
def get_similar_jobs(
    job_id: int,
    k: int = Query(default=6, ge=1, le=20),
    same_company: bool = Query(default=False),
):
    with SessionLocal() as session:
        if not session.get(JobListing, job_id):
            raise HTTPException(status_code=404, detail="Job not found")
        # Synthetic rows and postings scraped since the last index build
        # have no vector yet — say so rather than returning a silent [].
        if not session.get(JobVector, job_id):
            return {"indexed": False, "similar": []}
        return {"indexed": True, "similar": similar_jobs(session, job_id, k, same_company)}


@app.get("/rag/search")
def rag_search(
    q: str = Query(min_length=2, max_length=300),
    mode: str = Query(default="hybrid", pattern="^(dense|lexical|hybrid)$"),
    k: int = Query(default=10, ge=1, le=50),
):
    """Retrieval only, no LLM — for inspecting what each retriever returns."""
    with SessionLocal() as session:
        hits = SEARCHERS[mode](session, q, k)
    return {"mode": mode, "results": [h.to_dict() for h in hits]}


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.post("/rag/ask")
async def rag_ask(req: AskRequest, request: Request):
    api_key = configured_groq_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")

    client_ip = get_client_ip(request)
    allowed, retry_after = rate_limit(get_redis(), f"ratelimit:rag-ask:{client_ip}", limit=10, window_seconds=600)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many questions — try again in {retry_after}s")

    # retrieve → generate → check citations (→ retry once) — see ai/answer_graph.py
    state = await _answer_graph(api_key).ainvoke({"question": req.question.strip()})
    if state["status"] == "error":
        # Most often Groq's free-tier tokens-per-minute cap on the answer model.
        raise HTTPException(status_code=503, detail="The answer model is unavailable right now "
                                                    "(likely rate-limited) — try again in a minute.")
    cited = set(state.get("cited", []))
    return {
        "answer": state["answer"],
        "status": state["status"],
        "attempts": state.get("attempts", 0),
        "sources": [
            {"n": n, "job_id": s["job_id"], "title": s["title"], "company": s["company"],
             "url": s["url"], "section": s["section"], "snippet": s["body"], "cited": n in cited}
            for n, s in enumerate(state.get("sources", []), start=1)
        ],
    }


# ── Resume PDF extraction ────────────────────────────────────────────────────

@app.post("/resume/extract-text")
async def extract_resume_text(file: UploadFile = File(...)):
    """Extract plain text from a PDF or TXT upload. Handles LaTeX-generated PDFs."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    data = await file.read()
    fname = file.filename.lower()

    if fname.endswith('.txt') or file.content_type == 'text/plain':
        try:
            return {"text": data.decode('utf-8', errors='replace')}
        except Exception as e:
            raise HTTPException(422, f"Could not read text file: {e}")

    if fname.endswith('.pdf') or file.content_type == 'application/pdf':
        try:
            import io
            import pdfplumber
            text_parts = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text(x_tolerance=2, y_tolerance=2)
                    if t:
                        text_parts.append(t)
            text = '\n'.join(text_parts).strip()
            if not text:
                raise HTTPException(422, "PDF appears to have no extractable text (scanned image?)")
            return {"text": text}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(422, f"Could not extract PDF text: {e}")

    raise HTTPException(415, "Only PDF and TXT files are supported")


# ── Resume compatibility checker ────────────────────────────────────────────

class ResumeRequest(BaseModel):
    resume_text: str
    job_description: Optional[str] = None
    job_id: Optional[int] = None


_RESUME_SYSTEM = (
    "You are an expert resume coach specializing in software engineering roles. "
    "Analyze the resume against the job description and return ONLY a valid JSON object — "
    "no markdown, no code fences, no text outside the JSON."
)

_RESUME_PROMPT = """\
Analyze this resume against the job description and return the following JSON (no extra text):
{{
  "score": <integer 0-100>,
  "score_reasoning": "<one concise sentence explaining the score>",
  "matched_skills": ["<skill>"],
  "missing_skills": ["<skill>"],
  "sections": {{
    "summary": {{
      "found": <true|false>,
      "issues": "<what needs improvement, or null>",
      "rewrite": "<improved version aligned to the job, or null>"
    }},
    "skills": {{
      "found": <true|false>,
      "issues": "<what is weak or absent>",
      "to_add": ["<skill>"],
      "suggestion": "<how to restructure the skills section>"
    }},
    "experience": {{
      "found": <true|false>,
      "issues": "<overall weakness>",
      "rewrites": [
        {{"before": "<original bullet>", "after": "<improved bullet>", "reason": "<why>"}}
      ]
    }},
    "education": {{
      "found": <true|false>,
      "issues": "<issue or null>",
      "suggestion": "<advice or null>"
    }},
    "projects": {{
      "found": <true|false>,
      "issues": "<issue or null>",
      "suggestion": "<advice on what to add or highlight>"
    }}
  }},
  "top_suggestions": ["<suggestion 1>", "<suggestion 2>", "<suggestion 3>"]
}}

RESUME:
---
{resume}
---

JOB DESCRIPTION:
---
{job}
---"""


def _extract_json(text: str) -> dict:
    """Parse JSON from model output, tolerating markdown code fences."""
    try:
        return json_lib.loads(text)
    except Exception:
        pass
    # Strip ```json ... ``` wrappers
    stripped = re_module.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re_module.MULTILINE)
    try:
        return json_lib.loads(stripped)
    except Exception:
        pass
    # Last resort: grab first {...} block
    m = re_module.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json_lib.loads(m.group(0))
        except Exception:
            pass
    raise ValueError("Could not parse JSON from model response")


@app.post("/resume/analyze")
async def analyze_resume(req: ResumeRequest, request: Request):
    api_key = configured_groq_key()
    if not api_key:
        raise HTTPException(503, "GROQ_API_KEY not configured — add it to .env")

    client_ip = get_client_ip(request)
    allowed, retry_after = rate_limit(get_redis(), f"ratelimit:resume-analyze:{client_ip}", limit=5, window_seconds=600)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit reached for resume analysis — try again in {retry_after}s",
        )

    job_desc = (req.job_description or "").strip()

    if req.job_id and not job_desc:
        with SessionLocal() as session:
            j = session.get(JobListing, req.job_id)
            if j:
                job_desc = j.description or f"{j.title} at {j.company}"

    if not job_desc:
        raise HTTPException(400, "job_description or job_id is required")

    resume_text = req.resume_text[:5000]
    job_text    = job_desc[:3000]

    prompt = _RESUME_PROMPT.format(resume=resume_text, job=job_text)

    from groq import Groq
    client = Groq(api_key=api_key)
    loop   = asyncio.get_event_loop()

    def _sync():
        model = "openai/gpt-oss-120b"
        resp = client.chat.completions.create(
            model=model,
            max_tokens=3000,
            temperature=0.1,
            messages=[
                {"role": "system", "content": _RESUME_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            **reasoning_kwargs(model),
        )
        return (resp.choices[0].message.content or "").strip()

    try:
        raw    = await loop.run_in_executor(None, _sync)
        result = _extract_json(raw)
        return result
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}
