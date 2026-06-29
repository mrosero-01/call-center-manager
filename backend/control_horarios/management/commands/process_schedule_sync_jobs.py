from django.core.management.base import BaseCommand

from control_horarios.application.sync_jobs import process_schedule_sync_jobs
from control_horarios.infrastructure.asterisk.factories import build_schedule_publisher


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
        result = process_schedule_sync_jobs(
            limit=options["limit"],
            retry_failed=options["retry_failed"],
            max_attempts=options["max_attempts"],
            publisher=build_schedule_publisher(),
        )

        if result["processed"] == 0:
            self.stdout.write("No hay trabajos de sincronizacion pendientes.")
            return

        for job in result["synced_jobs"]:
            self.stdout.write(self.style.SUCCESS(f"Job {job.id} sincronizado."))

        for failed_job in result["failed_jobs"]:
            self.stdout.write(
                self.style.ERROR(
                    f"Job {failed_job['job'].id} fallo: {failed_job['error']}"
                )
            )

        self.stdout.write(
            "Procesados: {processed}. Sincronizados: {synced}. Fallidos: {failed}.".format(
                **result
            )
        )
