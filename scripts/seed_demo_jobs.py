"""Seed the database with the realistic sample jobs from
frontend/src/data/mockJobs.js — useful for demoing the UI without a
RapidAPI/JSearch key. Safe to re-run: dedupes on source_job_id like a
normal scrape.

Usage: python scripts/seed_demo_jobs.py
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.base import Job
from db.session import init_db, SessionLocal
from db.save import save_jobs

MOCK_JOBS_JS = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data" / "mockJobs.js"


def load_mock_jobs() -> list[dict]:
    script = (
        f"import('{MOCK_JOBS_JS.as_uri()}').then(m => "
        "process.stdout.write(JSON.stringify(m.mockJobs)))"
    )
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def main():
    init_db()
    raw_jobs = load_mock_jobs()

    jobs = [
        Job(
            source_job_id=j["source_job_id"],
            title=j["title"],
            company=j["company"],
            source=j["source"],
            url=j["url"],
            posted_at=j.get("posted_at"),
            city=j.get("city"),
            state=j.get("state"),
            country=j.get("country"),
            is_remote=j.get("is_remote"),
            work_mode=j.get("work_mode"),
            job_type=j.get("job_type"),
            experience_level=j.get("experience_level"),
            description=j.get("description"),
            responsibilities=j.get("responsibilities") or [],
            qualifications=j.get("qualifications") or [],
            benefits=j.get("benefits") or [],
            salary_min=j.get("salary_min"),
            salary_max=j.get("salary_max"),
            salary_currency=j.get("salary_currency"),
            salary_period=j.get("salary_period"),
            required_skills=j.get("required_skills") or [],
            visa_sponsorship=j.get("visa_sponsorship"),
        )
        for j in raw_jobs
    ]

    with SessionLocal() as session:
        saved, skipped = save_jobs(jobs, session)

    print(f"Seeded {saved} jobs ({skipped} already present).")


if __name__ == "__main__":
    main()
