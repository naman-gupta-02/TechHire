"""Ashby job-board API — https://api.ashbyhq.com/posting-api

Public, unauthenticated, documented for external consumption. Each real
company runs its own board at this URL; nothing here touches Indeed,
Glassdoor, or any site that prohibits scraping.
"""
import requests

from .ats_common import html_to_text
from .base import Job
from .parse import extract_job, is_cs_job

BOARD_NAMES = {
    "ramp": "Ramp", "notion": "Notion", "plaid": "Plaid",
    "linear": "Linear", "openai": "OpenAI", "hex": "Hex",
}

_EMPLOYMENT_TYPE_MAP = {
    "fulltime": "FULLTIME",
    "parttime": "PARTTIME",
    "intern": "INTERN",
    "internship": "INTERN",
    "contract": "CONTRACTOR",
    "temporary": "CONTRACTOR",
}


def _to_raw(job: dict, company_name: str) -> dict:
    raw_type = (job.get("employmentType") or "").lower().replace("-", "").replace(" ", "")
    employment_type = _EMPLOYMENT_TYPE_MAP.get(raw_type)
    location = job.get("location") or ""
    description = job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml") or "")

    return {
        "job_id": f"ashby-{job['id']}",
        "job_title": job.get("title") or "N/A",
        "employer_name": company_name,
        "job_apply_link": job.get("jobUrl") or job.get("applyUrl") or "",
        "job_posted_at_datetime_utc": job.get("publishedAt"),
        "job_location": location,
        "job_is_remote": bool(job.get("isRemote")) or "remote" in location.lower(),
        "job_employment_types": [employment_type] if employment_type else [],
        "job_description": description,
    }


def fetch(board: str, existing_ids=None, **_ignored) -> tuple[list[Job], bool]:
    """Pull all open postings from one company's Ashby job board."""
    existing_ids = existing_ids or set()
    company_name = BOARD_NAMES.get(board, board.title())

    try:
        res = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{board}",
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"  ⚠ Ashby/{board} request failed: {e}")
        return [], False

    if res.status_code == 429:
        print(f"  ✗ Ashby/{board} rate limited")
        return [], True
    if res.status_code != 200:
        print(f"  ⚠ Ashby/{board} API error {res.status_code}")
        return [], False

    raw_jobs = res.json().get("jobs", [])
    jobs = []
    for j in raw_jobs:
        raw = _to_raw(j, company_name)
        if raw["job_id"] in existing_ids:
            continue
        if not is_cs_job(raw["job_title"]):
            continue
        jobs.append(extract_job(raw, source="ashby"))

    print(f"  → {len(jobs)} new CS jobs from Ashby/{board} ({len(raw_jobs)} total postings)")
    return jobs, False
