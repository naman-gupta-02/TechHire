"""Lever job-board API — https://api.lever.co/v0/postings

Public, unauthenticated, documented for external consumption. Each real
company runs its own board at this URL; nothing here touches Indeed,
Glassdoor, or any site that prohibits scraping.
"""
from datetime import datetime, timezone

import requests

from .ats_common import html_to_text
from .base import Job
from .parse import extract_job, is_cs_job

BOARD_NAMES = {
    "palantir": "Palantir",
}

_COMMITMENT_TO_TYPE = {
    "full-time": "FULLTIME",
    "part-time": "PARTTIME",
    "internship": "INTERN",
    "intern": "INTERN",
    "contract": "CONTRACTOR",
    "temporary": "CONTRACTOR",
}


def _to_raw(job: dict, company_name: str) -> dict:
    categories = job.get("categories") or {}
    commitment = (categories.get("commitment") or "").lower()
    employment_type = _COMMITMENT_TO_TYPE.get(commitment)

    posted_at = None
    created_ms = job.get("createdAt")
    if created_ms:
        posted_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).isoformat()

    parts = [job.get("descriptionPlain") or "", job.get("additionalPlain") or ""]
    for item in job.get("lists") or []:
        label = item.get("text") or ""
        body = html_to_text(item.get("content") or "")
        if body:
            parts.append(f"\n{label}\n{body}")
    description = "\n\n".join(p for p in parts if p)

    location = categories.get("location") or ""

    return {
        "job_id": f"lever-{job['id']}",
        "job_title": job.get("text") or "N/A",
        "employer_name": company_name,
        "job_apply_link": job.get("hostedUrl") or job.get("applyUrl") or "",
        "job_posted_at_datetime_utc": posted_at,
        "job_location": location,
        "job_is_remote": job.get("workplaceType") == "remote" or "remote" in location.lower(),
        "job_employment_types": [employment_type] if employment_type else [],
        "job_description": description,
    }


def fetch(board: str, existing_ids=None, **_ignored) -> tuple[list[Job], bool]:
    """Pull all open postings from one company's Lever job board."""
    existing_ids = existing_ids or set()
    company_name = BOARD_NAMES.get(board, board.title())

    try:
        res = requests.get(
            f"https://api.lever.co/v0/postings/{board}",
            params={"mode": "json"},
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"  ⚠ Lever/{board} request failed: {e}")
        return [], False

    if res.status_code == 429:
        print(f"  ✗ Lever/{board} rate limited")
        return [], True
    if res.status_code != 200:
        print(f"  ⚠ Lever/{board} API error {res.status_code}")
        return [], False

    raw_jobs = res.json()
    if not isinstance(raw_jobs, list):
        raw_jobs = []

    jobs = []
    for j in raw_jobs:
        raw = _to_raw(j, company_name)
        if raw["job_id"] in existing_ids:
            continue
        if not is_cs_job(raw["job_title"]):
            continue
        jobs.append(extract_job(raw, source="lever"))

    print(f"  → {len(jobs)} new CS jobs from Lever/{board} ({len(raw_jobs)} total postings)")
    return jobs, False
