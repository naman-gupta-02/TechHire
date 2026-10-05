from scraper.base import Job
from db.save import save_jobs


def _job(source_job_id="job-1", **overrides):
    defaults = dict(
        source_job_id=source_job_id,
        title="Backend Engineer",
        company="Acme Corp",
        source="indeed",
        url="https://example.com/job-1",
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_new_jobs_are_saved(db_session):
    saved, skipped = save_jobs([_job("a"), _job("b"), _job("c")], db_session)
    assert saved == 3
    assert skipped == 0


def test_duplicate_source_job_id_is_skipped(db_session):
    save_jobs([_job("dup-1")], db_session)
    saved, skipped = save_jobs([_job("dup-1"), _job("new-1")], db_session)
    assert saved == 1
    assert skipped == 1


def test_missing_source_job_id_is_skipped(db_session):
    saved, skipped = save_jobs([_job(source_job_id="")], db_session)
    assert saved == 0
    assert skipped == 1


def test_mixed_batch_saves_only_new_ones(db_session):
    save_jobs([_job("x"), _job("y")], db_session)
    saved, skipped = save_jobs([_job("x"), _job("y"), _job("z")], db_session)
    assert saved == 1
    assert skipped == 2
