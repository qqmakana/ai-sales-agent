import time
from datetime import datetime, timedelta

from app import app
from database import db, Automation
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from job_queue import get_queue, queue_enabled
from scheduler_utils import compute_next_run


def _tables_ready() -> bool:
    try:
        db.session.execute(text("SELECT 1 FROM automations LIMIT 1"))
        return True
    except ProgrammingError:
        db.session.rollback()
        return False


def enqueue_due_jobs():
    if not queue_enabled():
        return

    queue = get_queue()
    if not queue:
        return

    now = datetime.utcnow()
    lock_expiry = now - timedelta(minutes=10)

    with app.app_context():
        if not _tables_ready():
            return

        due = (
            Automation.query.filter(Automation.is_active.is_(True))
            .filter(Automation.frequency != "once")
            .filter(Automation.next_run_at.isnot(None))
            .filter(Automation.next_run_at <= now)
            .all()
        )

        for automation in due:
            if automation.locked_at and automation.locked_at > lock_expiry:
                continue

            automation.locked_at = now
            automation.status = "queued"
            db.session.commit()

            queue.enqueue("tasks.run_automation_task", automation.id)


def backfill_next_runs():
    """Ensure scheduled automations have next_run_at set."""
    with app.app_context():
        if not _tables_ready():
            return

        scheduled = (
            Automation.query.filter(Automation.is_active.is_(True))
            .filter(Automation.frequency != "once")
            .all()
        )
        for automation in scheduled:
            if not automation.next_run_at:
                automation.next_run_at = compute_next_run(
                    automation.frequency,
                    automation.scheduled_time,
                    automation.scheduled_days,
                    from_time=datetime.utcnow(),
                )
        db.session.commit()


if __name__ == "__main__":
    if not queue_enabled():
        print("[SCHEDULER] REDIS_URL not set. Scheduler is disabled.")
    else:
        print("[SCHEDULER] Starting scheduler loop...")
        backfill_next_runs()
        while True:
            enqueue_due_jobs()
            time.sleep(30)
