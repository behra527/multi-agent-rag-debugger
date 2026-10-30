from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import JobRecord
from app.domain.enums import JobStatus


def recover_interrupted_jobs(db: Session) -> int:
    """Mark jobs left in running/queued-in-process state after a crash."""
    stale = (
        db.query(JobRecord)
        .filter(JobRecord.status.in_([JobStatus.RUNNING.value]))
        .all()
    )
    count = 0
    for job in stale:
        job.status = JobStatus.FAILED.value
        job.error_message = "Interrupted by application restart."
        job.finished_at = datetime.now(timezone.utc)
        count += 1
    if count:
        db.commit()
    return count
