"""Background jobs (D25): a row in the jobs table and a thread in the same process.
At most one job of each kind runs; boot_id tells which server run started a job."""
import logging
import sqlite3
import threading
from contextlib import closing


class AlreadyRunning(Exception):
    pass


def _thread(work):
    threading.Thread(target=work, daemon=True).start()


class JobRunner:
    def __init__(self, db, clock, boot_id, spawn=None):
        self._db = db
        self._clock = clock
        self._boot_id = boot_id
        # Tests pass their own spawn, to run the job at once.
        self._spawn = spawn or _thread

    def start(self, kind, work):
        """Add a running job, start work() in the background and return the job id at once."""
        try:
            with closing(self._db.connect()) as conn, conn:
                # The unique index allows only one running job of a kind.
                job_id = conn.execute(
                    "INSERT INTO jobs (kind, status, boot_id, created_at) VALUES (?, 'running', ?, ?)",
                    (kind, self._boot_id, self._clock.now_iso()),
                ).lastrowid
        except sqlite3.IntegrityError:
            raise AlreadyRunning(kind) from None
        self._spawn(lambda: self._run(job_id, work))
        return job_id

    def _run(self, job_id, work):
        status, error = "done", None
        try:
            work()
        except Exception as failure:
            status, error = "failed", type(failure).__name__
            # The class name only: the message or traceback of an HTTP error can hold the API key.
            logging.getLogger("uvicorn.error").error("Job %d failed: %s", job_id, error)
        with closing(self._db.connect()) as conn, conn:
            conn.execute(
                "UPDATE jobs SET status = ?, error = ?, finished_at = ? WHERE id = ? AND status = 'running'",
                (status, error, self._clock.now_iso(), job_id),
            )

    def status(self, job_id):
        return self._one("SELECT * FROM jobs WHERE id = ?", job_id)

    def latest(self, kind):
        """The newest job of the kind, or None."""
        return self._one("SELECT * FROM jobs WHERE kind = ? ORDER BY id DESC LIMIT 1", kind)

    def _one(self, sql, value):
        with closing(self._db.connect()) as conn:
            row = conn.execute(sql, (value,)).fetchone()
        return dict(row) if row else None

    def fail_dead_jobs(self):
        """Called at start: a running job of an earlier server run will never finish."""
        with closing(self._db.connect()) as conn, conn:
            conn.execute(
                "UPDATE jobs SET status = 'failed', error = 'server restarted', finished_at = ? "
                "WHERE status = 'running' AND boot_id != ?",
                (self._clock.now_iso(), self._boot_id),
            )
