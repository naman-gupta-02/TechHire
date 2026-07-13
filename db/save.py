from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from scraper.base import Job
from .models import JobListing


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def save_jobs(jobs: list[Job], session: Session) -> tuple[int, int]:
    saved = skipped = 0

    # Load all existing IDs up front — one query instead of N
    existing_ids: set[str] = {
        row[0] for row in session.query(JobListing.source_job_id).all()
    }

    for job in jobs:
        if not job.source_job_id or job.source_job_id in existing_ids:
            skipped += 1
            continue

        session.add(JobListing(
            source_job_id    = job.source_job_id,
            title            = job.title,
            company          = job.company,
            source           = job.source,
            url              = job.url,
            posted_at        = _parse_dt(job.posted_at),
            expires_at       = _parse_dt(job.expires_at),
            city             = job.city,
            state            = job.state,
            country          = job.country,
            is_remote        = job.is_remote,
            work_mode        = job.work_mode,
            job_type         = job.job_type,
            experience_level = job.experience_level,
            description      = job.description,
            responsibilities = job.responsibilities or [],
            qualifications   = job.qualifications or [],
            benefits         = job.benefits or [],
            salary_min       = job.salary_min,
            salary_max       = job.salary_max,
            salary_currency  = job.salary_currency,
            salary_period    = job.salary_period,
            required_skills  = job.required_skills or [],
            visa_sponsorship = job.visa_sponsorship,
            start_date_text  = job.start_date_text,
            scraped_at       = datetime.now(timezone.utc),
        ))
        existing_ids.add(job.source_job_id)
        saved += 1

    session.commit()
    return saved, skipped
