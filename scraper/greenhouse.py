"""Greenhouse job-board API — https://boards-api.greenhouse.io

Public, unauthenticated, documented for external consumption. Each real
company runs its own board at this URL; nothing here touches Indeed,
Glassdoor, or any site that prohibits scraping.
"""
import requests

from .ats_common import html_to_text
from .base import Job
from .parse import extract_job, is_cs_job

BOARD_NAMES = {
    "stripe": "Stripe", "airbnb": "Airbnb", "coinbase": "Coinbase",
    "robinhood": "Robinhood", "affirm": "Affirm", "gitlab": "GitLab",
    "asana": "Asana", "brex": "Brex", "pinterest": "Pinterest",
    "reddit": "Reddit", "cloudflare": "Cloudflare", "figma": "Figma",
    "databricks": "Databricks", "discord": "Discord", "dropbox": "Dropbox",
    "instacart": "Instacart", "lyft": "Lyft", "twitch": "Twitch",
    "datadog": "Datadog", "mongodb": "MongoDB", "squarespace": "Squarespace",
}


def _to_raw(job: dict, company_name: str) -> dict:
    location_name = (job.get("location") or {}).get("name") or ""
    return {
        "job_id": f"greenhouse-{job['id']}",
        "job_title": job.get("title") or "N/A",
        "employer_name": job.get("company_name") or company_name,
        "job_apply_link": job.get("absolute_url") or "",
        "job_posted_at_datetime_utc": job.get("first_published") or job.get("updated_at"),
        "job_location": location_name,
        "job_is_remote": "remote" in location_name.lower(),
        "job_employment_types": [],
        "job_description": html_to_text(job.get("content") or ""),
    }


def fetch(board: str, existing_ids=None, **_ignored) -> tuple[list[Job], bool]:
    """Pull all open postings from one company's Greenhouse job board."""
    existing_ids = existing_ids or set()
    company_name = BOARD_NAMES.get(board, board.title())

    try:
        res = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
            params={"content": "true"},
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"  ⚠ Greenhouse/{board} request failed: {e}")
        return [], False

    if res.status_code == 429:
        print(f"  ✗ Greenhouse/{board} rate limited")
        return [], True
    if res.status_code != 200:
        print(f"  ⚠ Greenhouse/{board} API error {res.status_code}")
        return [], False

    raw_jobs = res.json().get("jobs", [])
    jobs = []
    for j in raw_jobs:
        raw = _to_raw(j, company_name)
        if raw["job_id"] in existing_ids:
            continue
        if not is_cs_job(raw["job_title"]):
            continue
        jobs.append(extract_job(raw, source="greenhouse"))

    print(f"  → {len(jobs)} new CS jobs from Greenhouse/{board} ({len(raw_jobs)} total postings)")
    return jobs, False
