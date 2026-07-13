from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    # Required
    source_job_id: str
    title:         str
    company:       str
    source:        str
    url:           str

    # Timestamps (ISO strings from API — parsed to datetime on DB write)
    posted_at:  Optional[str] = None
    expires_at: Optional[str] = None

    # Location
    city:      Optional[str]  = None
    state:     Optional[str]  = None
    country:   Optional[str]  = None
    is_remote: Optional[bool] = None
    work_mode: Optional[str]  = None   # remote / hybrid / onsite

    # Role
    job_type:         Optional[str]  = None   # FULLTIME / INTERN / CONTRACT
    experience_level: Optional[str]  = None   # intern / entry / mid / senior
    description:      Optional[str]  = None
    responsibilities: list            = field(default_factory=list)
    qualifications:   list            = field(default_factory=list)
    benefits:         list            = field(default_factory=list)

    # Compensation
    salary_min:      Optional[float] = None
    salary_max:      Optional[float] = None
    salary_currency: Optional[str]   = None
    salary_period:   Optional[str]   = None   # YEAR / HOUR / MONTH

    # Skills
    required_skills: list = field(default_factory=list)

    # International students
    visa_sponsorship: Optional[bool] = None

    # Employment start (e.g. "Summer 2026", "January 2026")
    start_date_text: Optional[str] = None
