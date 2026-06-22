import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from control_horarios.infrastructure.asterisk.ami_client import (
    AmiClientError,
    SocketAmiClient,
)


class Command(BaseCommand):
    help = "Inspecciona AstDB y contextos del dialplan de Asterisk usando AMI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--horario",
            action="store_true",
            help="Muestra claves existentes en AstDB bajo la familia horario.",
        )
        parser.add_argument(
            "--contexts",
            action="store_true",
            help="Lista contextos detectados en el dialplan.",
        )
        parser.add_argument(
            "--raw",
            action="store_true",
            help="Muestra la salida cruda de Asterisk.",
        )

    def handle(self, *args, **options):
        show_horario = options["horario"] or not options["contexts"]
        show_contexts = options["contexts"] or not options["horario"]
        client = self._build_client()

        try:
            if show_horario:
                self._show_horario_database(client, raw=options["raw"])

            if show_contexts:
                self._show_dialplan_contexts(client, raw=options["raw"])
        except (AmiClientError, OSError) as exc:
            raise CommandError(f"No se pudo inspeccionar Asterisk: {exc}") from exc

    def _build_client(self):
        if not settings.ASTERISK_AMI_HOST:
            raise CommandError("ASTERISK_AMI_HOST no esta configurado.")

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

    def _show_horario_database(self, client, raw):
        output = client.command("database show horario")

        self.stdout.write(self.style.MIGRATE_HEADING("AstDB /horario"))
        if raw:
            self.stdout.write(output)
            return

        keys = sorted(set(re.findall(r"(/horario/[^\s:]+)", output)))
        if not keys:
            self.stdout.write("No se encontraron claves bajo /horario.")
            return

        for key in keys:
            self.stdout.write(f"- {key}")

    def _show_dialplan_contexts(self, client, raw):
        output = client.command("dialplan show")

        self.stdout.write(self.style.MIGRATE_HEADING("Contextos del dialplan"))
        if raw:
            self.stdout.write(output)
            return

        contexts = sorted(set(re.findall(r"^\[ Context '([^']+)'", output, re.MULTILINE)))
        if not contexts:
            self.stdout.write("No se detectaron contextos en la salida del dialplan.")
            return

        for context in contexts:
            self.stdout.write(f"- {context}")
