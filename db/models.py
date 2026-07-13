from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Boolean, Float, DateTime, Integer
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import mapped_column, Mapped
from .session import Base


class JobListing(Base):
    __tablename__ = "job_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Unique identifier from JSearch — prevents duplicate inserts
    source_job_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Core
    title:   Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    source:  Mapped[str] = mapped_column(String(100))   # "indeed", "lever", etc.
    url:     Mapped[str] = mapped_column(Text)

    # Timestamps
    posted_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime]           = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Location
    city:      Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    state:     Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    country:   Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    is_remote: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    work_mode: Mapped[Optional[str]]  = mapped_column(String(20), nullable=True)  # remote / hybrid / onsite

    # Role details
    job_type:         Mapped[Optional[str]]  = mapped_column(String(50), nullable=True)   # FULLTIME, INTERN, CONTRACT
    experience_level: Mapped[Optional[str]]  = mapped_column(String(20), nullable=True)   # intern / entry / mid / senior
    description:      Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    responsibilities: Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True)
    qualifications:   Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True)
    benefits:         Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True)

    # Compensation
    salary_min:      Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max:      Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[Optional[str]]   = mapped_column(String(10), nullable=True)
    salary_period:   Mapped[Optional[str]]   = mapped_column(String(20), nullable=True)  # YEAR / HOUR / MONTH

    # Skills
    required_skills: Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True)

    # International students
    visa_sponsorship: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Employment start info extracted from title/description (e.g. "Summer 2026")
    start_date_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # AI-generated summary (cached)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
