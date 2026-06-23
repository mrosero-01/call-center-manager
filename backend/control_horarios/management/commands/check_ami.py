from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from control_horarios.infrastructure.asterisk.ami_client import (
    AmiClientError,
    SocketAmiClient,
)
from control_horarios.infrastructure.asterisk.schedule_formatter import (
    ASTDB_SCHEDULE_FAMILY,
)


class Command(BaseCommand):
    help = "Verifica conexion AMI y una escritura controlada en AstDB."

    test_key = "__django_check__/Ping"
    test_value = "00:00-00:01"

    def handle(self, *args, **options):
        client = self._build_client()

        try:
            self.stdout.write("1. Conectando y escribiendo clave temporal en AstDB...")
            client.db_put(
                family=ASTDB_SCHEDULE_FAMILY,
                key=self.test_key,
                value=self.test_value,
            )

            self.stdout.write("2. Leyendo AstDB para confirmar la escritura...")
            output = client.command(f"database show {ASTDB_SCHEDULE_FAMILY}")
            self._ensure_test_key_is_present(output)

            self.stdout.write("3. Borrando clave temporal...")
            client.db_del(
                family=ASTDB_SCHEDULE_FAMILY,
                key=self.test_key,
            )
        except (AmiClientError, OSError) as exc:
            raise CommandError(f"Check AMI fallido: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                "AMI OK: login, DBPut, lectura CLI y DBDel funcionaron correctamente."
            )
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

    def _ensure_test_key_is_present(self, output):
        expected_path = f"/{ASTDB_SCHEDULE_FAMILY}/{self.test_key}"

        if expected_path not in output or self.test_value not in output:
            raise CommandError(
                f"AMI escribio la clave temporal, pero no se pudo confirmar {expected_path}."
            )
