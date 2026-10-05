from datetime import datetime, timedelta, timezone

from api import _build_query
from tests.conftest import make_job

DEFAULTS = dict(
    search="", skills=[], visa_only=False, salary_min=0, salary_max=300000,
    work_modes=[], experience_levels=[], date_posted="any", seasons=[],
)


def result_ids(session, **overrides):
    """Run _build_query and return the matching ids as a set.

    Uses set membership rather than exact list/set equality against the
    full result set, deliberately — this table may hold other rows
    (seeded demo/synthetic data, other tests' leftovers) beyond the two
    jobs a given test cares about, and asserting exact equality against
    the whole table would make tests depend on it being otherwise empty.
    """
    kwargs = {**DEFAULTS, **overrides}
    stmt = _build_query(**kwargs)
    return {j.id for j in session.scalars(stmt).all()}


def seed_two_jobs(session):
    now = datetime.now(timezone.utc)
    job1 = make_job(
        session,
        source_job_id="q-job-1",
        title="Backend Engineer",
        company="Acme Corp",
        work_mode="remote",
        experience_level="entry",
        visa_sponsorship=True,
        salary_min=90000,
        salary_max=110000,
        required_skills=["python", "sql"],
        posted_at=now,
        start_date_text="Summer 2026",
    )
    job2 = make_job(
        session,
        source_job_id="q-job-2",
        title="Frontend Developer",
        company="Globex",
        work_mode="onsite",
        experience_level="senior",
        visa_sponsorship=False,
        salary_min=130000,
        salary_max=160000,
        required_skills=["javascript", "react"],
        posted_at=now - timedelta(days=31),
        start_date_text=None,
    )
    return job1, job2


def test_search_matches_title_case_insensitively(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, search="BACKEND")
    assert job1.id in ids
    assert job2.id not in ids


def test_search_matches_company(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, search="globex")
    assert job2.id in ids
    assert job1.id not in ids


def test_skills_filter(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, skills=["python"])
    assert job1.id in ids
    assert job2.id not in ids


def test_visa_only_filter(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, visa_only=True)
    assert job1.id in ids
    assert job2.id not in ids


def test_salary_min_filter_excludes_lower_paying_job(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, salary_min=100000)
    assert job2.id in ids
    assert job1.id not in ids


def test_salary_max_filter_excludes_higher_paying_job(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, salary_max=120000)
    assert job1.id in ids
    assert job2.id not in ids


def test_work_mode_filter(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, work_modes=["remote"])
    assert job1.id in ids
    assert job2.id not in ids


def test_experience_level_filter(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, experience_levels=["senior"])
    assert job2.id in ids
    assert job1.id not in ids


def test_date_posted_cutoff_excludes_older_job(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, date_posted="24h")
    assert job1.id in ids
    assert job2.id not in ids


def test_date_posted_any_returns_all(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, date_posted="any")
    assert job1.id in ids
    assert job2.id in ids


def test_seasons_filter(db_session):
    job1, job2 = seed_two_jobs(db_session)
    ids = result_ids(db_session, seasons=["summer 2026"])
    assert job1.id in ids
    assert job2.id not in ids
