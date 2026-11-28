"""Tests of the background jobs (D25): status, one running job per kind, dead jobs after a restart."""
import threading

import pytest

from app.jobs import AlreadyRunning, JobRunner


def now_run(work):
    work()


def never_run(work):
    pass


def test_job_done(db, clock):
    runner = JobRunner(db, clock, "boot-a", spawn=now_run)
    done = []
    job_id = runner.start("summary", lambda: done.append(1))
    job = runner.status(job_id)
    assert done == [1] and job["status"] == "done" and job["finished_at"]
    assert runner.latest("summary")["id"] == job_id
    assert runner.latest("class_review") is None


def test_job_failed(db, clock):
    def work():
        raise RuntimeError("secret detail")

    runner = JobRunner(db, clock, "boot-a", spawn=now_run)
    job = runner.status(runner.start("summary", work))
    assert job["status"] == "failed" and job["error"] == "RuntimeError"


def test_default_spawn_runs_in_the_background(db, clock):
    release, done = threading.Event(), threading.Event()

    def work():
        release.wait(5)
        done.set()

    runner = JobRunner(db, clock, "boot-a")
    job_id = runner.start("summary", work)
    assert runner.status(job_id)["status"] == "running"
    release.set()
    assert done.wait(5)


# TC-74: a second start while one is running is refused.
def test_second_start_refused_tc74(db, clock):
    runner = JobRunner(db, clock, "boot-a", spawn=never_run)
    runner.start("summary", lambda: None)
    with pytest.raises(AlreadyRunning):
        runner.start("summary", lambda: None)
    assert runner.start("class_review", lambda: None)


# TC-75: a running job of an earlier server run is failed (D25).
def test_dead_job_failed_tc75(db, clock):
    old = JobRunner(db, clock, "boot-a", spawn=never_run)
    job_id = old.start("summary", lambda: None)
    old.fail_dead_jobs()
    assert old.status(job_id)["status"] == "running"

    new = JobRunner(db, clock, "boot-b", spawn=never_run)
    new.fail_dead_jobs()
    assert new.status(job_id)["status"] == "failed"
    assert new.start("summary", lambda: None)
