from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from control_horarios.infrastructure.asterisk.ami_client import (
    AmiClientError,
    SocketAmiClient,
)
from control_horarios.infrastructure.asterisk.astdb_importer import (
    parse_astdb_schedule_rows,
)
from control_horarios.models import (
    CallCenterLocation,
    OperationSchedule,
    OperationScheduleDay,
    Tenant,
)


class Command(BaseCommand):
    help = "Importa horarios existentes desde AstDB /horario hacia Django."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-code",
            required=True,
            help="Codigo del tenant al que se asociaran los lugares importados.",
        )
        parser.add_argument(
            "--tenant-name",
            help="Nombre del tenant si debe crearse.",
        )
        parser.add_argument(
            "--family",
            help="Importa solo una familia AstDB, por ejemplo callcenter_principal.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra lo que importaria sin guardar cambios.",
        )

    def handle(self, *args, **options):
        client = self._build_client()

        try:
            output = client.command("database show horario")
        except (AmiClientError, OSError) as exc:
            raise CommandError(f"No se pudo leer AstDB: {exc}") from exc

        rows = parse_astdb_schedule_rows(output)
        if options["family"]:
            rows = [
                row
                for row in rows
                if row["astdb_family"] == options["family"]
            ]

        grouped_rows = self._group_rows_by_family(rows)
        if not grouped_rows:
            self.stdout.write("No se encontraron horarios semanales para importar.")
            return

        if options["dry_run"]:
            self._print_plan(grouped_rows)
            return

        tenant = self._get_or_create_tenant(
            code=options["tenant_code"],
            name=options["tenant_name"],
        )
        imported_count = self._import_grouped_rows(tenant, grouped_rows)

        self.stdout.write(
            self.style.SUCCESS(f"Horarios importados: {imported_count}")
        )

    def _build_client(self):
        if not settings.ASTERISK_AMI_USERNAME or not settings.ASTERISK_AMI_PASSWORD:
            raise CommandError(
                "ASTERISK_AMI_USERNAME y ASTERISK_AMI_PASSWORD son obligatorios."
            )

        return SocketAmiClient(
            host=settings.ASTERISK_AMI_HOST,
            port=settings.ASTERISK_AMI_PORT,
            username=settings.ASTERISK_AMI_USERNAME,
            password=settings.ASTERISK_AMI_PASSWORD,
            timeout=settings.ASTERISK_AMI_TIMEOUT,
        )

    def _group_rows_by_family(self, rows):
        grouped_rows = defaultdict(list)

        for row in rows:
            grouped_rows[row["astdb_family"]].append(row)

        return grouped_rows

    def _print_plan(self, grouped_rows):
        for astdb_family, rows in grouped_rows.items():
            self.stdout.write(f"{astdb_family}:")
            for row in rows:
                self.stdout.write(f"  {row['day_of_week']}: {row['ranges']}")

    def _get_or_create_tenant(self, code, name):
        tenant, _created = Tenant.objects.get_or_create(
            code=code,
            defaults={"name": name or code.upper()},
        )

        return tenant

    @transaction.atomic
    def _import_grouped_rows(self, tenant, grouped_rows):
        imported_count = 0

        for astdb_family, rows in grouped_rows.items():
            location, _created = CallCenterLocation.objects.get_or_create(
                astdb_family=astdb_family,
                defaults={
                    "tenant": tenant,
                    "name": self._humanize_family(astdb_family),
                    "code": astdb_family,
                },
            )
            schedule, _created = OperationSchedule.objects.update_or_create(
                tenant=location.tenant,
                location=location,
                defaults={"timezone": settings.TIME_ZONE},
            )

            for row in rows:
                OperationScheduleDay.objects.update_or_create(
                    schedule=schedule,
                    day_of_week=row["day_of_week"],
                    defaults={"ranges": row["ranges"]},
                )
                imported_count += 1

        return imported_count

    def _humanize_family(self, astdb_family):
        return astdb_family.replace("_", " ").title()
