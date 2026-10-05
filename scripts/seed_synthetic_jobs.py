"""Seed the database with a large synthetic dataset for realistic
performance testing — the 22 hand-written demo jobs are too small to show
what the query planner and Redis cache actually do at production scale.

Usage:
    python scripts/seed_synthetic_jobs.py --count 5000
"""
import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.base import Job
from db.session import init_db, SessionLocal
from db.save import save_jobs

TITLES = [
    "Software Engineer", "Backend Engineer", "Frontend Engineer", "Full Stack Engineer",
    "Data Engineer", "Machine Learning Engineer", "DevOps Engineer", "Site Reliability Engineer",
    "Platform Engineer", "Security Engineer", "iOS Engineer", "Android Engineer",
    "Cloud Engineer", "QA Engineer", "Software Engineer Intern", "Data Science Intern",
    "New Grad Software Engineer", "Entry Level Software Engineer",
]

COMPANIES = [
    "Google", "Stripe", "Airbnb", "Lyft", "Meta", "Amazon", "Microsoft", "Netflix",
    "Datadog", "Snowflake", "Databricks", "Figma", "Notion", "Plaid", "Ramp", "Brex",
    "Rippling", "Vercel", "Cloudflare", "MongoDB", "Confluent", "HashiCorp", "Robinhood",
    "DoorDash", "Instacart", "Coinbase", "Affirm", "Block", "Palantir", "Scale AI",
]

SKILLS_POOL = [
    "python", "javascript", "typescript", "react", "node.js", "go", "java", "kotlin",
    "swift", "aws", "gcp", "azure", "kubernetes", "docker", "terraform", "sql",
    "postgresql", "redis", "kafka", "spark", "pytorch", "tensorflow", "graphql", "rust",
    "c++", "ci/cd", "microservices", "distributed systems", "django", "fastapi",
    "system design", "grpc", "elasticsearch", "airflow",
]

CITIES = [
    ("San Francisco", "CA"), ("New York", "NY"), ("Seattle", "WA"), ("Austin", "TX"),
    ("Boston", "MA"), ("Chicago", "IL"), ("Denver", "CO"), ("Los Angeles", "CA"),
    (None, None),  # fully remote, no city
]

WORK_MODES = ["remote", "remote", "hybrid", "hybrid", "onsite"]
EXPERIENCE_LEVELS = ["intern", "entry", "entry", "mid", "mid", "senior"]
JOB_TYPES = ["FULLTIME", "FULLTIME", "FULLTIME", "INTERN", "CONTRACT"]
SOURCES = ["indeed", "glassdoor", "handshake", "lever"]

SALARY_BANDS = {
    "intern": (6000, 9000, "MONTH"),
    "entry": (95000, 140000, "YEAR"),
    "mid": (140000, 190000, "YEAR"),
    "senior": (180000, 260000, "YEAR"),
}


def make_synthetic_job(i: int) -> Job:
    title = random.choice(TITLES)
    company = random.choice(COMPANIES)
    experience_level = random.choice(EXPERIENCE_LEVELS)
    work_mode = random.choice(WORK_MODES)
    city, state = random.choice(CITIES)
    skills = random.sample(SKILLS_POOL, k=random.randint(3, 7))
    posted_days_ago = random.randint(0, 90)

    salary_min = salary_max = salary_period = None
    if random.random() > 0.15:  # ~85% of postings list a salary
        lo, hi, period = SALARY_BANDS[experience_level]
        band_width = hi - lo
        salary_min = lo + random.randint(0, band_width // 2)
        salary_max = salary_min + random.randint(band_width // 10, band_width // 3)
        salary_period = period

    return Job(
        source_job_id=f"synthetic-{i}",
        title=title,
        company=company,
        source=random.choice(SOURCES),
        url=f"https://example.com/jobs/synthetic-{i}",
        posted_at=(datetime.now(timezone.utc) - timedelta(days=posted_days_ago)).isoformat(),
        city=city,
        state=state,
        country="US",
        is_remote=work_mode == "remote",
        work_mode=work_mode,
        job_type=random.choice(JOB_TYPES),
        experience_level=experience_level,
        description=(
            f"{company} is hiring a {title}. You'll work with {', '.join(skills)} "
            f"on a team shipping production systems at scale. This is a {work_mode} "
            f"role for {experience_level}-level candidates.\n\n"
            f"Requirements: experience with {', '.join(skills[:3])}, strong "
            f"communication skills, and a track record of shipping."
        ),
        responsibilities=[f"Build and maintain systems using {s}" for s in skills[:3]],
        qualifications=[f"Experience with {s}" for s in skills],
        benefits=["Health insurance", "401k match", "Equity", "Flexible PTO"],
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="USD" if salary_min else None,
        salary_period=salary_period,
        required_skills=skills,
        visa_sponsorship=random.choice([True, False, None]),
        start_date_text=random.choice([None, None, "Summer 2026", "Fall 2026", "January 2027"]),
    )


def main():
    parser = argparse.ArgumentParser(description="Seed a large synthetic job dataset")
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42, help="random seed, for reproducible datasets")
    args = parser.parse_args()

    random.seed(args.seed)
    init_db()

    jobs = [make_synthetic_job(i) for i in range(args.count)]

    with SessionLocal() as session:
        saved, skipped = save_jobs(jobs, session)

    print(f"Seeded {saved} synthetic jobs ({skipped} already present).")


if __name__ == "__main__":
    main()
