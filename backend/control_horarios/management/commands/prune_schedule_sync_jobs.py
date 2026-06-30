from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from control_horarios.models import ScheduleSyncJob


class Command(BaseCommand):
    help = "Elimina jobs sincronizados antiguos sin tocar pendientes ni fallidos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=90,
            help="Borra jobs sincronizados con mas dias que este valor.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra cuantos borraria sin eliminar registros.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["older_than_days"])
        queryset = ScheduleSyncJob.objects.filter(
            status=ScheduleSyncJob.Status.SYNCED,
            updated_at__lt=cutoff,
        )
        count = queryset.count()

        if options["dry_run"]:
            self.stdout.write(f"Jobs sincronizados antiguos a eliminar: {count}")
            return

        queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Jobs sincronizados eliminados: {count}"))
