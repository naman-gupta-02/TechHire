import time
from datetime import datetime
from sqlalchemy import select
from scraper import indeed, glassdoor, handshake, lever
from scraper.utils import filter_alive
from db.session import init_db, SessionLocal
from db.models import JobListing
from db.save import save_jobs
from db.reparse import reparse_all


# Each entry: (display_name, module, fetch_kwargs)
# Multiple queries per source to get diverse roles.
# max_pages is a safety cap — with existing_ids passed in, fetch() stops
# early once it reaches jobs we've already scraped.
SCRAPE_CONFIGS = [
    # Full-time roles
    ("Indeed",    indeed,    {"query": "software engineer",        "location": "remote", "max_pages": 5}),
    ("Indeed",    indeed,    {"query": "backend engineer",         "location": "remote", "max_pages": 3}),
    ("Indeed",    indeed,    {"query": "frontend engineer",        "location": "remote", "max_pages": 3}),
    ("Indeed",    indeed,    {"query": "data engineer",            "location": "remote", "max_pages": 3}),
    ("Indeed",    indeed,    {"query": "machine learning engineer","location": "remote", "max_pages": 2}),
    # Intern roles — Indeed
    ("Indeed",    indeed,    {"query": "software engineer intern", "location": "remote", "max_pages": 3}),
    ("Indeed",    indeed,    {"query": "data science intern",      "location": "remote", "max_pages": 2}),
    ("Indeed",    indeed,    {"query": "machine learning intern",  "location": "remote", "max_pages": 2}),

    # Full-time roles — Glassdoor
    ("Glassdoor", glassdoor, {"query": "software engineer",        "location": "remote", "max_pages": 5}),
    ("Glassdoor", glassdoor, {"query": "backend engineer",         "location": "remote", "max_pages": 3}),
    ("Glassdoor", glassdoor, {"query": "data engineer",            "location": "remote", "max_pages": 3}),
    # Intern roles — Glassdoor
    ("Glassdoor", glassdoor, {"query": "software engineering intern","location": "remote","max_pages": 3}),
    ("Glassdoor", glassdoor, {"query": "software developer intern", "location": "remote","max_pages": 2}),

    # Handshake — already targets new grads and interns
    ("Handshake", handshake, {"query": "software engineer",        "location": "remote", "max_pages": 5}),
    ("Handshake", handshake, {"query": "new grad software engineer","location": "remote","max_pages": 3}),
    ("Handshake", handshake, {"query": "entry level engineer",     "location": "remote", "max_pages": 3}),
    ("Handshake", handshake, {"query": "software engineer intern", "location": "remote", "max_pages": 3}),

    # Full-time + intern roles — Lever
    ("Lever",     lever,     {"query": "software engineer",        "location": "remote", "max_pages": 5}),
    ("Lever",     lever,     {"query": "backend engineer",         "location": "remote", "max_pages": 3}),
    ("Lever",     lever,     {"query": "fullstack engineer",       "location": "remote", "max_pages": 3}),
    ("Lever",     lever,     {"query": "software engineer intern", "location": "remote", "max_pages": 3}),
]


def _scrape_all(existing_ids: set[str]) -> tuple[list, dict[str, int], bool]:
    all_jobs = []
    source_counts: dict[str, int] = {}
    quota_exceeded = False

    for name, module, kwargs in SCRAPE_CONFIGS:
        label = f"{name} ({kwargs['query']})"
        print(f"Fetching {label}...")
        try:
            jobs, hit_quota = module.fetch(existing_ids=existing_ids, **kwargs)
            all_jobs.extend(jobs)
            source_counts[name] = source_counts.get(name, 0) + len(jobs)
            print(f"  → {len(jobs)} jobs")
            if hit_quota:
                quota_exceeded = True
                print("  ✗ JSearch monthly quota exhausted — stopping remaining queries")
                break
        except Exception as e:
            print(f"  ✗ Failed: {e}")
        time.sleep(3)  # pause between query batches

    return all_jobs, source_counts, quota_exceeded


def run():
    """Full scrape — used for the CLI / cron. Still skips jobs we already
    have (via existing_ids early-stop) so re-running isn't wasteful."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting scrape...\n")

    init_db()
    with SessionLocal() as session:
        existing_ids = set(session.scalars(select(JobListing.source_job_id)).all())

    all_jobs, source_counts, quota_exceeded = _scrape_all(existing_ids)

    print(f"\nTotal scraped: {len(all_jobs)} jobs")
    for src, count in source_counts.items():
        print(f"  {src}: {count}")
    if quota_exceeded:
        print("  ⚠ Stopped early: JSearch monthly quota exhausted")

    print("\nChecking URLs...")
    all_jobs = filter_alive(all_jobs)
    print(f"  → {len(all_jobs)} jobs with live links")

    print("\nSaving to database...")
    with SessionLocal() as session:
        saved, skipped = save_jobs(all_jobs, session)

    print(f"  ✓ Saved:   {saved}")
    print(f"  ↷ Skipped: {skipped} (duplicates)")

    print("\nReparsing fields on all jobs...")
    reparse_result = reparse_all()
    print(f"  ✓ Reparsed: {reparse_result['updated']} updated, {reparse_result['unchanged']} unchanged")
    print(f"\nDone.\n")


def refresh() -> dict:
    """
    Incremental refresh for the UI's Refresh button. Pages through each
    source until it hits a job already in the DB, then stops — only new
    postings get fetched, so repeated refreshes stay fast.
    Returns a summary dict (no stdout dependency, safe to call from the API).
    """
    init_db()
    with SessionLocal() as session:
        existing_ids = set(session.scalars(select(JobListing.source_job_id)).all())

    all_jobs, source_counts, quota_exceeded = _scrape_all(existing_ids)
    all_jobs = filter_alive(all_jobs)

    with SessionLocal() as session:
        saved, skipped = save_jobs(all_jobs, session)

    reparse_result = reparse_all()

    return {
        "scraped": len(all_jobs),
        "saved": saved,
        "skipped": skipped,
        "sources": source_counts,
        "quota_exceeded": quota_exceeded,
        "reparsed": reparse_result["updated"],
    }


if __name__ == "__main__":
    run()
