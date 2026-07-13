"""
One-time (and safe to re-run) migration: re-derive experience_level, job_type,
and start_date_text for all existing job_listings rows using the title and
description already stored in the DB.

We can't recover job_employment_types from the original API call, so
classification falls back to title regex — which is the same as what
new jobs get when the API type is FULLTIME but title says "intern".
"""
from sqlalchemy import select
from .session import init_db, SessionLocal
from .models import JobListing
from scraper.parse import _experience_level, _job_type, _start_date_text, _INTERN_RE, _SENIOR_RE, _ENTRY_RE


def _level_from_title(title: str) -> str:
    if _INTERN_RE.search(title):
        return "intern"
    if _SENIOR_RE.search(title):
        return "senior"
    if _ENTRY_RE.search(title):
        return "entry"
    return "mid"


def _type_from_title(title: str, current_type: str) -> str:
    # If already correctly set to CONTRACT/PARTTIME keep it (we don't store the API array)
    if current_type in ("CONTRACT", "PARTTIME"):
        return current_type
    if _INTERN_RE.search(title):
        return "INTERN"
    return "FULLTIME"


def reparse_all() -> dict:
    init_db()
    updated = 0
    unchanged = 0

    with SessionLocal() as session:
        jobs = session.scalars(select(JobListing)).all()

        for j in jobs:
            new_level     = _level_from_title(j.title or "")
            new_type      = _type_from_title(j.title or "", j.job_type or "FULLTIME")
            new_start     = _start_date_text(j.title or "", j.description or "")

            changed = (
                j.experience_level != new_level
                or j.job_type != new_type
                or j.start_date_text != new_start
            )

            if changed:
                j.experience_level = new_level
                j.job_type         = new_type
                j.start_date_text  = new_start
                updated += 1
            else:
                unchanged += 1

        session.commit()

    return {"updated": updated, "unchanged": unchanged, "total": updated + unchanged}


if __name__ == "__main__":
    result = reparse_all()
    print(f"Updated:   {result['updated']}")
    print(f"Unchanged: {result['unchanged']}")
    print(f"Total:     {result['total']}")
