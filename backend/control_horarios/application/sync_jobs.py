from django.db import transaction
from django.utils import timezone

from control_horarios.application.commands import ScheduleDayInput
from control_horarios.infrastructure.asterisk.ami_client import AmiClientError
from control_horarios.infrastructure.asterisk.factories import build_schedule_publisher
from control_horarios.models import OperationSchedule, ScheduleSyncJob


def get_processable_sync_jobs(limit=20, retry_failed=False, max_attempts=5):
    statuses = [ScheduleSyncJob.Status.PENDING]

    if retry_failed:
        statuses.append(ScheduleSyncJob.Status.FAILED)

    return list(
        ScheduleSyncJob.objects.select_related("tenant", "location", "schedule")
        .filter(status__in=statuses, attempts__lt=max_attempts)
        .order_by("created_at")[:limit]
    )


def process_schedule_sync_jobs(
    limit=20,
    retry_failed=False,
    max_attempts=5,
    publisher=None,
):
    publisher = publisher or build_schedule_publisher()
    jobs = get_processable_sync_jobs(
        limit=limit,
        retry_failed=retry_failed,
        max_attempts=max_attempts,
    )
    synced_jobs = []
    failed_jobs = []

    for job in jobs:
        try:
            _publish_job(publisher, job)
        except (AmiClientError, OSError, ValueError) as exc:
            _mark_failed(job, exc)
            failed_jobs.append({"job": job, "error": str(exc)})
        else:
            _mark_synced(job)
            synced_jobs.append(job)

    return {
        "processed": len(jobs),
        "synced": len(synced_jobs),
        "failed": len(failed_jobs),
        "synced_jobs": synced_jobs,
        "failed_jobs": failed_jobs,
    }


def process_schedule_sync_job(job, publisher=None):
    publisher = publisher or build_schedule_publisher()

    try:
        _publish_job(publisher, job)
    except (AmiClientError, OSError, ValueError) as exc:
        _mark_failed(job, exc)
        job.refresh_from_db()
        return {
            "synced": False,
            "job": job,
            "error": str(exc),
        }

    _mark_synced(job)
    job.refresh_from_db()
    return {
        "synced": True,
        "job": job,
        "error": "",
    }


def _publish_job(publisher, job):
    days = [
        ScheduleDayInput(
            day_of_week=day["day_of_week"],
            ranges=day["ranges"],
        )
        for day in job.payload.get("days", [])
    ]

    if not days:
        raise ValueError("El trabajo no contiene dias para sincronizar.")

    publisher.publish_days(
        astdb_family=job.location.astdb_family,
        days=days,
    )


@transaction.atomic
def _mark_synced(job):
    now = timezone.now()
    ScheduleSyncJob.objects.filter(id=job.id).update(
        status=ScheduleSyncJob.Status.SYNCED,
        attempts=job.attempts + 1,
        last_error="",
        synced_at=now,
    )
    if _is_latest_job_for_schedule(job):
        OperationSchedule.objects.filter(id=job.schedule_id).update(
            sync_status=OperationSchedule.SyncStatus.SYNCED,
            last_sync_error="",
            last_synced_at=now,
        )


@transaction.atomic
def _mark_failed(job, exc):
    error_message = str(exc)
    ScheduleSyncJob.objects.filter(id=job.id).update(
        status=ScheduleSyncJob.Status.FAILED,
        attempts=job.attempts + 1,
        last_error=error_message,
    )
    if _is_latest_job_for_schedule(job):
        OperationSchedule.objects.filter(id=job.schedule_id).update(
            sync_status=OperationSchedule.SyncStatus.FAILED,
            last_sync_error=error_message,
        )


def _is_latest_job_for_schedule(job):
    return not ScheduleSyncJob.objects.filter(
        schedule_id=job.schedule_id,
        id__gt=job.id,
    ).exists()
