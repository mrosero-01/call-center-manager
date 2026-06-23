from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from control_horarios.application.commands import ScheduleDayInput
from control_horarios.infrastructure.asterisk.ami_client import AmiClientError
from control_horarios.infrastructure.asterisk.factories import build_schedule_publisher
from control_horarios.models import OperationSchedule, ScheduleSyncJob


class Command(BaseCommand):
    help = "Procesa trabajos pendientes de sincronizacion de horarios hacia Asterisk."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Numero maximo de trabajos a procesar.",
        )
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Incluye trabajos fallidos con intentos disponibles.",
        )
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=5,
            help="Maximo de intentos por trabajo.",
        )

    def handle(self, *args, **options):
        publisher = build_schedule_publisher()
        jobs = self._get_jobs(
            limit=options["limit"],
            retry_failed=options["retry_failed"],
            max_attempts=options["max_attempts"],
        )

        if not jobs:
            self.stdout.write("No hay trabajos de sincronizacion pendientes.")
            return

        synced_count = 0
        failed_count = 0

        for job in jobs:
            try:
                self._publish_job(publisher, job)
            except (AmiClientError, OSError, ValueError) as exc:
                failed_count += 1
                self._mark_failed(job, exc)
                self.stdout.write(
                    self.style.ERROR(f"Job {job.id} fallo: {exc}")
                )
            else:
                synced_count += 1
                self._mark_synced(job)
                self.stdout.write(
                    self.style.SUCCESS(f"Job {job.id} sincronizado.")
                )

        self.stdout.write(
            f"Procesados: {len(jobs)}. Sincronizados: {synced_count}. Fallidos: {failed_count}."
        )

    def _get_jobs(self, limit, retry_failed, max_attempts):
        statuses = [ScheduleSyncJob.Status.PENDING]

        if retry_failed:
            statuses.append(ScheduleSyncJob.Status.FAILED)

        return list(
            ScheduleSyncJob.objects.select_related("location", "schedule")
            .filter(status__in=statuses, attempts__lt=max_attempts)
            .order_by("created_at")[:limit]
        )

    def _publish_job(self, publisher, job):
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
    def _mark_synced(self, job):
        now = timezone.now()
        ScheduleSyncJob.objects.filter(id=job.id).update(
            status=ScheduleSyncJob.Status.SYNCED,
            attempts=job.attempts + 1,
            last_error="",
            synced_at=now,
        )
        OperationSchedule.objects.filter(id=job.schedule_id).update(
            sync_status=OperationSchedule.SyncStatus.SYNCED,
            last_sync_error="",
            last_synced_at=now,
        )

    @transaction.atomic
    def _mark_failed(self, job, exc):
        error_message = str(exc)
        ScheduleSyncJob.objects.filter(id=job.id).update(
            status=ScheduleSyncJob.Status.FAILED,
            attempts=job.attempts + 1,
            last_error=error_message,
        )
        OperationSchedule.objects.filter(id=job.schedule_id).update(
            sync_status=OperationSchedule.SyncStatus.FAILED,
            last_sync_error=error_message,
        )
