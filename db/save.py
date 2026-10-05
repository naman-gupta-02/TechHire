from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String
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


def _clip(field_name: str, value: Optional[str]) -> Optional[str]:
    """Clip to the column's actual VARCHAR length. Free-text location/type
    fields from third-party APIs (e.g. a long combined-location string from
    a job board) can exceed our column widths — better to truncate than
    fail the whole insert batch."""
    if not isinstance(value, str):
        return value
    col_type = JobListing.__table__.columns[field_name].type
    if isinstance(col_type, String) and col_type.length and len(value) > col_type.length:
        return value[: col_type.length]
    return value


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
            source_job_id    = _clip("source_job_id", job.source_job_id),
            title            = _clip("title", job.title),
            company          = _clip("company", job.company),
            source           = _clip("source", job.source),
            url              = job.url,
            posted_at        = _parse_dt(job.posted_at),
            expires_at       = _parse_dt(job.expires_at),
            city             = _clip("city", job.city),
            state            = _clip("state", job.state),
            country          = _clip("country", job.country),
            is_remote        = job.is_remote,
            work_mode        = _clip("work_mode", job.work_mode),
            job_type         = _clip("job_type", job.job_type),
            experience_level = _clip("experience_level", job.experience_level),
            description      = job.description,
            responsibilities = job.responsibilities or [],
            qualifications   = job.qualifications or [],
            benefits         = job.benefits or [],
            salary_min       = job.salary_min,
            salary_max       = job.salary_max,
            salary_currency  = _clip("salary_currency", job.salary_currency),
            salary_period    = _clip("salary_period", job.salary_period),
            required_skills  = job.required_skills or [],
            visa_sponsorship = job.visa_sponsorship,
            start_date_text  = _clip("start_date_text", job.start_date_text),
            scraped_at       = datetime.now(timezone.utc),
        ))
        existing_ids.add(job.source_job_id)
        saved += 1

    session.commit()
    return saved, skipped
