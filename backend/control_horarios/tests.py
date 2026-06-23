from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.test import override_settings
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APITestCase

from .application.commands import ScheduleDayInput, UpdateOperationScheduleCommand
from .application.use_cases import UpdateOperationSchedule
from .infrastructure.asterisk.ami_client import AmiClientError, SocketAmiClient
from .infrastructure.asterisk.astdb_importer import parse_astdb_schedule_rows
from .infrastructure.asterisk.factories import build_schedule_publisher
from .infrastructure.asterisk.schedule_formatter import (
    build_schedule_astdb_key,
    build_schedule_astdb_path,
    build_schedule_astdb_value,
    format_ranges_for_astdb,
)
from .infrastructure.asterisk.schedule_publisher import (
    AmiSchedulePublisher,
    NoOpSchedulePublisher,
)
from .infrastructure.django.repositories import DjangoScheduleRepository
from .models import (
    CallCenterLocation,
    OperationSchedule,
    OperationScheduleDay,
    ScheduleChangeLog,
    Tenant,
    TenantMembership,
)


class FakeAmiClient:
    def __init__(self):
        self.db_put_calls = []

    def db_put(self, family, key, value):
        self.db_put_calls.append(
            {
                "family": family,
                "key": key,
                "value": value,
            }
        )


class FakeSocket:
    def __init__(self, responses, timeout_after_responses=False):
        self.responses = []
        for response in responses:
            if response is None:
                self.responses.append(None)
            else:
                self.responses.append(response.encode("utf-8"))

        self.sent_payloads = []
        self.timeout_after_responses = timeout_after_responses

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, payload):
        self.sent_payloads.append(payload.decode("utf-8"))

    def recv(self, buffer_size):
        if not self.responses:
            if self.timeout_after_responses:
                raise TimeoutError()

            return b""

        response = self.responses.pop(0)
        if response is None:
            raise TimeoutError()

        return response


class FakeScheduleRepository:
    def __init__(self):
        self.before_value = {
            "timezone": "America/Bogota",
            "days": {
                "Mon": [
                    {"start": "08:00", "end": "12:00"},
                ],
            },
        }
        self.saved_schedule = None
        self.change_logs = []

    def get_location_astdb_family(self, tenant_id, location_id):
        return "pas_aba_cla"

    def get_schedule_snapshot(self, tenant_id, location_id):
        return self.before_value

    def save_schedule(self, tenant_id, location_id, timezone, days):
        self.saved_schedule = {
            "tenant_id": tenant_id,
            "location_id": location_id,
            "timezone": timezone,
            "days": days,
        }
        return {
            "timezone": timezone,
            "days": {
                day.day_of_week: list(day.ranges)
                for day in days
            },
        }

    def save_change_log(
        self,
        tenant_id,
        location_id,
        changed_by_id,
        reason,
        before_value,
        after_value,
    ):
        self.change_logs.append(
            {
                "tenant_id": tenant_id,
                "location_id": location_id,
                "changed_by_id": changed_by_id,
                "reason": reason,
                "before_value": before_value,
                "after_value": after_value,
            }
        )


class FakeSchedulePublisher:
    def __init__(self):
        self.published_days = []

    def publish_day(self, astdb_family, day_of_week, ranges):
        self.published_days.append(
            {
                "astdb_family": astdb_family,
                "day_of_week": day_of_week,
                "ranges": ranges,
            }
        )


class FailingSchedulePublisher:
    def publish_day(self, astdb_family, day_of_week, ranges):
        raise AmiClientError("AMI no disponible")


class AstdbScheduleFormatterTests(SimpleTestCase):
    def test_formats_ranges_as_astdb_value(self):
        ranges = [
            {"start": "08:00", "end": "12:00"},
            {"start": "14:00", "end": "18:00"},
        ]

        value = format_ranges_for_astdb(ranges)

        self.assertEqual(value, "08:00-12:00|14:00-18:00")

    def test_builds_schedule_astdb_path(self):
        path = build_schedule_astdb_path("pas_aba_cla", "Mon")

        self.assertEqual(path, "/horario/pas_aba_cla/Mon")

    def test_builds_schedule_astdb_key_for_ami(self):
        key = build_schedule_astdb_key("pas_aba_cla", "Mon")

        self.assertEqual(key, "pas_aba_cla/Mon")

    def test_builds_astdb_value_from_schedule_day(self):
        schedule_day = SimpleNamespace(
            ranges=[
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "23:59"},
            ]
        )

        value = build_schedule_astdb_value(schedule_day)

        self.assertEqual(value, "08:00-12:00|14:00-23:59")


class AstdbScheduleImporterTests(SimpleTestCase):
    def test_parses_weekly_schedule_rows_and_skips_legacy_keys(self):
        output = """
Output: /horario/callcenter_principal/cierre : 14
Output: /horario/callcenter_principal/Mon : 14:00-18:00|08:00-12:00
Output: /horario/callcenter_principal/Tue : 08:00-18:00
"""

        rows = parse_astdb_schedule_rows(output)

        self.assertEqual(
            rows,
            [
                {
                    "astdb_family": "callcenter_principal",
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "12:00"},
                        {"start": "14:00", "end": "18:00"},
                    ],
                },
                {
                    "astdb_family": "callcenter_principal",
                    "day_of_week": "Tue",
                    "ranges": [
                        {"start": "08:00", "end": "18:00"},
                    ],
                },
            ],
        )


class AmiSchedulePublisherTests(SimpleTestCase):
    def test_publishes_day_to_astdb_using_ami_db_put(self):
        ami_client = FakeAmiClient()
        publisher = AmiSchedulePublisher(ami_client)

        publisher.publish_day(
            astdb_family="pas_aba_cla",
            day_of_week="Mon",
            ranges=[
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )

        self.assertEqual(
            ami_client.db_put_calls,
            [
                {
                    "family": "horario",
                    "key": "pas_aba_cla/Mon",
                    "value": "08:00-12:00|14:00-18:00",
                }
            ],
        )


class SocketAmiClientTests(SimpleTestCase):
    def test_accepts_single_line_ami_banner_before_login(self):
        fake_socket = FakeSocket(
            responses=[
                "Asterisk Call Manager/5.0\r\n",
                None,
                "Response: Success\r\nMessage: Authentication accepted\r\n\r\n",
                "Response: Success\r\nMessage: Updated database successfully\r\n\r\n",
                "Response: Goodbye\r\n\r\n",
            ]
        )
        client = SocketAmiClient(
            host="127.0.0.1",
            port=5038,
            username="admin",
            password="secret",
        )

        with patch(
            "control_horarios.infrastructure.asterisk.ami_client.socket.create_connection",
            return_value=fake_socket,
        ):
            client.db_put(
                family="horario",
                key="pas_aba_cla/Mon",
                value="08:00-12:00",
            )

        sent_payload = "".join(fake_socket.sent_payloads)

        self.assertIn("Action: Login\r\n", sent_payload)

    def test_sends_login_dbput_and_logoff_actions(self):
        fake_socket = FakeSocket(
            responses=[
                "Asterisk Call Manager/5.0\r\n\r\n",
                "Response: Success\r\nMessage: Authentication accepted\r\n\r\n",
                "Response: Success\r\nMessage: Updated database successfully\r\n\r\n",
                "Response: Goodbye\r\n\r\n",
            ]
        )
        client = SocketAmiClient(
            host="127.0.0.1",
            port=5038,
            username="admin",
            password="secret",
        )

        with patch(
            "control_horarios.infrastructure.asterisk.ami_client.socket.create_connection",
            return_value=fake_socket,
        ) as create_connection:
            client.db_put(
                family="horario",
                key="pas_aba_cla/Mon",
                value="08:00-12:00|14:00-18:00",
            )

        create_connection.assert_called_once_with(("127.0.0.1", 5038), timeout=5)
        sent_payload = "".join(fake_socket.sent_payloads)

        self.assertIn("Action: Login\r\n", sent_payload)
        self.assertIn("Username: admin\r\n", sent_payload)
        self.assertIn("Secret: secret\r\n", sent_payload)
        self.assertIn("Action: DBPut\r\n", sent_payload)
        self.assertIn("Family: horario\r\n", sent_payload)
        self.assertIn("Key: pas_aba_cla/Mon\r\n", sent_payload)
        self.assertIn("Val: 08:00-12:00|14:00-18:00\r\n", sent_payload)
        self.assertIn("Action: Logoff\r\n", sent_payload)

    def test_sends_readonly_cli_command_action(self):
        fake_socket = FakeSocket(
            responses=[
                "Asterisk Call Manager/5.0\r\n\r\n",
                "Response: Success\r\nMessage: Authentication accepted\r\n\r\n",
                "Response: Success\r\nOutput: /horario/pas_aba_cla/Mon\r\n\r\n",
                "Response: Goodbye\r\n\r\n",
            ]
        )
        client = SocketAmiClient(
            host="127.0.0.1",
            port=5038,
            username="admin",
            password="secret",
        )

        with patch(
            "control_horarios.infrastructure.asterisk.ami_client.socket.create_connection",
            return_value=fake_socket,
        ):
            response = client.command("database show horario")

        sent_payload = "".join(fake_socket.sent_payloads)

        self.assertIn("Action: Command\r\n", sent_payload)
        self.assertIn("Command: database show horario\r\n", sent_payload)
        self.assertIn("/horario/pas_aba_cla/Mon", response)


class SchedulePublisherFactoryTests(SimpleTestCase):
    @override_settings(ASTERISK_AMI_ENABLED=False)
    def test_builds_noop_publisher_when_ami_is_disabled(self):
        publisher = build_schedule_publisher()

        self.assertIsInstance(publisher, NoOpSchedulePublisher)

    @override_settings(
        ASTERISK_AMI_ENABLED=True,
        ASTERISK_AMI_HOST="10.0.0.5",
        ASTERISK_AMI_PORT=5038,
        ASTERISK_AMI_USERNAME="admin",
        ASTERISK_AMI_PASSWORD="secret",
        ASTERISK_AMI_TIMEOUT=3,
    )
    def test_builds_ami_publisher_when_ami_is_enabled(self):
        publisher = build_schedule_publisher()

        self.assertIsInstance(publisher, AmiSchedulePublisher)


class UpdateOperationScheduleTests(SimpleTestCase):
    def test_updates_schedule_logs_reason_and_publishes_days(self):
        repository = FakeScheduleRepository()
        publisher = FakeSchedulePublisher()
        use_case = UpdateOperationSchedule(repository, publisher)
        command = UpdateOperationScheduleCommand(
            tenant_id=1,
            location_id=10,
            changed_by_id=7,
            reason="  Extension por campana especial  ",
            timezone="America/Bogota",
            days=[
                ScheduleDayInput(
                    day_of_week="Mon",
                    ranges=[
                        {"start": "08:00", "end": "12:00"},
                        {"start": "14:00", "end": "20:00"},
                    ],
                ),
                ScheduleDayInput(
                    day_of_week="Tue",
                    ranges=[
                        {"start": "08:00", "end": "18:00"},
                    ],
                ),
            ],
        )

        result = use_case.execute(command)

        self.assertEqual(result["timezone"], "America/Bogota")
        self.assertEqual(repository.saved_schedule["tenant_id"], 1)
        self.assertEqual(repository.saved_schedule["location_id"], 10)
        self.assertEqual(repository.change_logs[0]["reason"], "Extension por campana especial")
        self.assertEqual(repository.change_logs[0]["before_value"], repository.before_value)
        self.assertEqual(repository.change_logs[0]["after_value"], result)
        self.assertEqual(
            publisher.published_days,
            [
                {
                    "astdb_family": "pas_aba_cla",
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "12:00"},
                        {"start": "14:00", "end": "20:00"},
                    ],
                },
                {
                    "astdb_family": "pas_aba_cla",
                    "day_of_week": "Tue",
                    "ranges": [
                        {"start": "08:00", "end": "18:00"},
                    ],
                },
            ],
        )

    def test_requires_change_reason(self):
        repository = FakeScheduleRepository()
        publisher = FakeSchedulePublisher()
        use_case = UpdateOperationSchedule(repository, publisher)
        command = UpdateOperationScheduleCommand(
            tenant_id=1,
            location_id=10,
            changed_by_id=7,
            reason="   ",
            timezone="America/Bogota",
            days=[
                ScheduleDayInput(
                    day_of_week="Mon",
                    ranges=[
                        {"start": "08:00", "end": "12:00"},
                    ],
                ),
            ],
        )

        with self.assertRaisesMessage(ValueError, "El motivo del cambio es obligatorio."):
            use_case.execute(command)

    def test_orders_ranges_before_saving_and_publishing(self):
        repository = FakeScheduleRepository()
        publisher = FakeSchedulePublisher()
        use_case = UpdateOperationSchedule(repository, publisher)
        command = UpdateOperationScheduleCommand(
            tenant_id=1,
            location_id=10,
            changed_by_id=7,
            reason="Ordenar franjas",
            timezone="America/Bogota",
            days=[
                ScheduleDayInput(
                    day_of_week="Mon",
                    ranges=[
                        {"start": "14:00", "end": "18:00"},
                        {"start": "08:00", "end": "12:00"},
                    ],
                ),
            ],
        )

        use_case.execute(command)

        self.assertEqual(
            repository.saved_schedule["days"][0].ranges,
            [
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )
        self.assertEqual(
            publisher.published_days[0]["ranges"],
            [
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )

    def test_rejects_invalid_time_range(self):
        repository = FakeScheduleRepository()
        publisher = FakeSchedulePublisher()
        use_case = UpdateOperationSchedule(repository, publisher)
        command = UpdateOperationScheduleCommand(
            tenant_id=1,
            location_id=10,
            changed_by_id=7,
            reason="Cambio operativo",
            timezone="America/Bogota",
            days=[
                ScheduleDayInput(
                    day_of_week="Mon",
                    ranges=[
                        {"start": "18:00", "end": "12:00"},
                    ],
                ),
            ],
        )

        with self.assertRaisesMessage(ValueError, "El inicio del rango debe ser menor al fin."):
            use_case.execute(command)

    def test_rejects_overlapping_ranges(self):
        repository = FakeScheduleRepository()
        publisher = FakeSchedulePublisher()
        use_case = UpdateOperationSchedule(repository, publisher)
        command = UpdateOperationScheduleCommand(
            tenant_id=1,
            location_id=10,
            changed_by_id=7,
            reason="Rangos solapados",
            timezone="America/Bogota",
            days=[
                ScheduleDayInput(
                    day_of_week="Mon",
                    ranges=[
                        {"start": "08:00", "end": "12:00"},
                        {"start": "11:00", "end": "15:00"},
                    ],
                ),
            ],
        )

        with self.assertRaisesMessage(ValueError, "Las franjas horarias no pueden solaparse."):
            use_case.execute(command)

    def test_allows_closed_day_with_empty_ranges(self):
        repository = FakeScheduleRepository()
        publisher = FakeSchedulePublisher()
        use_case = UpdateOperationSchedule(repository, publisher)
        command = UpdateOperationScheduleCommand(
            tenant_id=1,
            location_id=10,
            changed_by_id=7,
            reason="Cerrar domingo",
            timezone="America/Bogota",
            days=[
                ScheduleDayInput(
                    day_of_week="Sun",
                    ranges=[],
                ),
            ],
        )

        result = use_case.execute(command)

        self.assertEqual(result["days"]["Sun"], [])
        self.assertEqual(publisher.published_days[0]["ranges"], [])


class DjangoScheduleRepositoryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="PAS", code="pas")
        self.location = CallCenterLocation.objects.create(
            tenant=self.tenant,
            name="ABA CLA",
            code="aba_cla",
            astdb_family="pas_aba_cla",
        )
        self.user = get_user_model().objects.create_user(
            username="operador",
            password="test-pass",
        )
        self.repository = DjangoScheduleRepository()

    def test_saves_schedule_and_returns_snapshot(self):
        result = self.repository.save_schedule(
            tenant_id=self.tenant.id,
            location_id=self.location.id,
            timezone="America/Bogota",
            days=[
                ScheduleDayInput(
                    day_of_week="Mon",
                    ranges=[
                        {"start": "08:00", "end": "12:00"},
                        {"start": "14:00", "end": "18:00"},
                    ],
                ),
                ScheduleDayInput(
                    day_of_week="Tue",
                    ranges=[
                        {"start": "08:00", "end": "18:00"},
                    ],
                ),
            ],
        )

        schedule = OperationSchedule.objects.get(location=self.location)

        self.assertEqual(result["timezone"], "America/Bogota")
        self.assertEqual(
            result["days"]["Mon"],
            [
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )
        self.assertEqual(schedule.days.count(), 2)

    def test_keeps_days_not_present_in_new_schedule(self):
        schedule = OperationSchedule.objects.create(
            tenant=self.tenant,
            location=self.location,
            timezone="America/Bogota",
        )
        OperationScheduleDay.objects.create(
            schedule=schedule,
            day_of_week="Mon",
            ranges=[{"start": "08:00", "end": "12:00"}],
        )
        OperationScheduleDay.objects.create(
            schedule=schedule,
            day_of_week="Wed",
            ranges=[{"start": "08:00", "end": "12:00"}],
        )

        result = self.repository.save_schedule(
            tenant_id=self.tenant.id,
            location_id=self.location.id,
            timezone="America/Bogota",
            days=[
                ScheduleDayInput(
                    day_of_week="Mon",
                    ranges=[
                        {"start": "10:00", "end": "16:00"},
                    ],
                ),
            ],
        )

        self.assertEqual(
            result["days"]["Mon"],
            [
                {"start": "10:00", "end": "16:00"},
            ],
        )
        self.assertEqual(
            result["days"]["Wed"],
            [
                {"start": "08:00", "end": "12:00"},
            ],
        )
        self.assertTrue(schedule.days.filter(day_of_week="Wed").exists())

    def test_gets_location_astdb_family(self):
        astdb_family = self.repository.get_location_astdb_family(
            tenant_id=self.tenant.id,
            location_id=self.location.id,
        )

        self.assertEqual(astdb_family, "pas_aba_cla")

    def test_saves_change_log(self):
        before_value = {"days": {"Mon": [{"start": "08:00", "end": "12:00"}]}}
        after_value = {"days": {"Mon": [{"start": "08:00", "end": "18:00"}]}}

        self.repository.save_change_log(
            tenant_id=self.tenant.id,
            location_id=self.location.id,
            changed_by_id=self.user.id,
            reason="Extension por campana especial",
            before_value=before_value,
            after_value=after_value,
        )

        change_log = ScheduleChangeLog.objects.get()

        self.assertEqual(change_log.tenant, self.tenant)
        self.assertEqual(change_log.location, self.location)
        self.assertEqual(change_log.changed_by, self.user)
        self.assertEqual(change_log.reason, "Extension por campana especial")
        self.assertEqual(change_log.before_value, before_value)
        self.assertEqual(change_log.after_value, after_value)


class ImportAstdbSchedulesCommandTests(TestCase):
    def test_imports_weekly_schedules_from_astdb(self):
        output = """
Response: Success
Output: /horario/callcenter_principal/cierre : 14
Output: /horario/callcenter_principal/Mon : 14:00-18:00|08:00-12:00
Output: /horario/callcenter_principal/Tue : 08:00-18:00
"""
        stdout = StringIO()

        with patch(
            "control_horarios.management.commands.import_astdb_schedules.SocketAmiClient.command",
            return_value=output,
        ):
            call_command(
                "import_astdb_schedules",
                tenant_code="pas",
                tenant_name="PAS",
                stdout=stdout,
            )

        tenant = Tenant.objects.get(code="pas")
        location = CallCenterLocation.objects.get(astdb_family="callcenter_principal")
        schedule = OperationSchedule.objects.get(location=location)

        self.assertEqual(location.tenant, tenant)
        self.assertEqual(
            schedule.days.get(day_of_week="Mon").ranges,
            [
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )
        self.assertEqual(
            schedule.days.get(day_of_week="Tue").ranges,
            [
                {"start": "08:00", "end": "18:00"},
            ],
        )
        self.assertIn("Horarios importados: 2", stdout.getvalue())

    def test_dry_run_does_not_write_data(self):
        output = "Output: /horario/callcenter_principal/Mon : 08:00-12:00"
        stdout = StringIO()

        with patch(
            "control_horarios.management.commands.import_astdb_schedules.SocketAmiClient.command",
            return_value=output,
        ):
            call_command(
                "import_astdb_schedules",
                tenant_code="pas",
                dry_run=True,
                stdout=stdout,
            )

        self.assertEqual(CallCenterLocation.objects.count(), 0)
        self.assertIn("callcenter_principal", stdout.getvalue())


class OperationScheduleApiTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="PAS", code="pas")
        self.location = CallCenterLocation.objects.create(
            tenant=self.tenant,
            name="ABA CLA",
            code="aba_cla",
            astdb_family="pas_aba_cla",
        )
        self.user = get_user_model().objects.create_user(
            username="contratista",
            password="test-pass",
        )
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.ADMIN,
        )
        self.url = reverse(
            "operation-schedule-update",
            kwargs={"location_id": self.location.id},
        )
        self.locations_url = reverse("callcenter-location-list")
        self.change_logs_url = reverse(
            "schedule-change-log-list",
            kwargs={"location_id": self.location.id},
        )

    def test_member_can_update_operation_schedule(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "timezone": "America/Bogota",
            "reason": "Extension por campana especial",
            "days": [
                {
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "12:00"},
                        {"start": "14:00", "end": "20:00"},
                    ],
                },
                {
                    "day_of_week": "Tue",
                    "ranges": [
                        {"start": "08:00", "end": "18:00"},
                    ],
                },
            ],
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["timezone"], "America/Bogota")
        self.assertEqual(
            response.data["days"]["Mon"],
            [
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "20:00"},
            ],
        )
        self.assertEqual(OperationSchedule.objects.count(), 1)
        self.assertEqual(OperationScheduleDay.objects.count(), 2)
        self.assertEqual(ScheduleChangeLog.objects.count(), 1)
        self.assertEqual(
            ScheduleChangeLog.objects.get().reason,
            "Extension por campana especial",
        )

    def test_lists_locations_available_to_admin_user(self):
        other_tenant = Tenant.objects.create(name="OTRO", code="otro")
        CallCenterLocation.objects.create(
            tenant=other_tenant,
            name="Otro callcenter",
            code="otro_callcenter",
            astdb_family="otro_callcenter",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.locations_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.location.id)
        self.assertEqual(response.data[0]["astdb_family"], "pas_aba_cla")

    def test_superuser_lists_all_locations(self):
        other_tenant = Tenant.objects.create(name="OTRO", code="otro")
        CallCenterLocation.objects.create(
            tenant=other_tenant,
            name="Otro callcenter",
            code="otro_callcenter",
            astdb_family="otro_callcenter",
        )
        superuser = get_user_model().objects.create_superuser(
            username="owner",
            password="test-pass",
        )
        self.client.force_authenticate(user=superuser)

        response = self.client.get(self.locations_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_gets_current_operation_schedule(self):
        schedule = OperationSchedule.objects.create(
            tenant=self.tenant,
            location=self.location,
            timezone="America/Bogota",
        )
        OperationScheduleDay.objects.create(
            schedule=schedule,
            day_of_week="Mon",
            ranges=[
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["location"]["id"], self.location.id)
        self.assertEqual(response.data["timezone"], "America/Bogota")
        self.assertEqual(
            response.data["days"]["Mon"],
            [
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )

    def test_api_orders_ranges_before_saving(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "timezone": "America/Bogota",
            "reason": "Ordenar franjas",
            "days": [
                {
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "14:00", "end": "18:00"},
                        {"start": "08:00", "end": "12:00"},
                    ],
                },
            ],
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["days"]["Mon"],
            [
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )

    def test_api_rejects_overlapping_ranges(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "timezone": "America/Bogota",
            "reason": "Solape accidental",
            "days": [
                {
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "12:00"},
                        {"start": "11:00", "end": "15:00"},
                    ],
                },
            ],
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("days", response.data)

    def test_api_accepts_closed_day_with_empty_ranges(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "timezone": "America/Bogota",
            "reason": "Cerrar domingo",
            "days": [
                {
                    "day_of_week": "Sun",
                    "ranges": [],
                },
            ],
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["days"]["Sun"], [])

    def test_api_returns_502_when_asterisk_sync_fails(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "timezone": "America/Bogota",
            "reason": "Prueba error AMI",
            "days": [
                {
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "12:00"},
                    ],
                },
            ],
        }

        with patch(
            "control_horarios.views.build_schedule_publisher",
            return_value=FailingSchedulePublisher(),
        ):
            response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertIn("asterisk_error", response.data)
        self.assertEqual(OperationSchedule.objects.count(), 1)

    def test_api_keeps_omitted_existing_days(self):
        schedule = OperationSchedule.objects.create(
            tenant=self.tenant,
            location=self.location,
            timezone="America/Bogota",
        )
        OperationScheduleDay.objects.create(
            schedule=schedule,
            day_of_week="Tue",
            ranges=[
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )
        self.client.force_authenticate(user=self.user)
        payload = {
            "timezone": "America/Bogota",
            "reason": "Cambio solo de lunes",
            "days": [
                {
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "20:00"},
                    ],
                },
            ],
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["days"]["Tue"],
            [
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        )
        self.assertTrue(
            OperationScheduleDay.objects.filter(
                schedule=schedule,
                day_of_week="Tue",
            ).exists()
        )

    def test_user_without_membership_cannot_update_schedule(self):
        other_user = get_user_model().objects.create_user(
            username="externo",
            password="test-pass",
        )
        self.client.force_authenticate(user=other_user)
        payload = {
            "timezone": "America/Bogota",
            "reason": "Cambio operativo",
            "days": [
                {
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "12:00"},
                    ],
                },
            ],
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(OperationSchedule.objects.count(), 0)
        self.assertEqual(ScheduleChangeLog.objects.count(), 0)

    def test_operator_membership_cannot_update_schedule(self):
        operator = get_user_model().objects.create_user(
            username="operador-tenant",
            password="test-pass",
        )
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=operator,
            role=TenantMembership.Role.OPERATOR,
        )
        self.client.force_authenticate(user=operator)
        payload = {
            "timezone": "America/Bogota",
            "reason": "Cambio operativo",
            "days": [
                {
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "12:00"},
                    ],
                },
            ],
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(OperationSchedule.objects.count(), 0)
        self.assertEqual(ScheduleChangeLog.objects.count(), 0)

    def test_api_requires_change_reason(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "timezone": "America/Bogota",
            "reason": "",
            "days": [
                {
                    "day_of_week": "Mon",
                    "ranges": [
                        {"start": "08:00", "end": "12:00"},
                    ],
                },
            ],
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.data)

    def test_lists_schedule_change_logs_for_allowed_location(self):
        ScheduleChangeLog.objects.create(
            tenant=self.tenant,
            location=self.location,
            changed_by=self.user,
            reason="Cambio de prueba",
            before_value={"days": {}},
            after_value={"days": {"Mon": []}},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.change_logs_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["changed_by"], self.user.username)
        self.assertEqual(response.data[0]["reason"], "Cambio de prueba")

    def test_user_without_membership_cannot_view_schedule_change_logs(self):
        other_user = get_user_model().objects.create_user(
            username="auditor-externo",
            password="test-pass",
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.get(self.change_logs_url)

        self.assertEqual(response.status_code, 403)


class SessionAuthApiTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="PAS", code="pas")
        self.user = get_user_model().objects.create_user(
            username="miguel",
            password="test-pass",
        )
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.ADMIN,
        )

    def test_login_creates_session_and_me_returns_user(self):
        login_response = self.client.post(
            reverse("auth-login"),
            {
                "username": "miguel",
                "password": "test-pass",
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.data["username"], "miguel")
        self.assertFalse(login_response.data["is_superuser"])
        self.assertEqual(login_response.data["memberships"][0]["role"], "admin")

        me_response = self.client.get(reverse("current-user"))

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["username"], "miguel")
        self.assertEqual(me_response.data["memberships"][0]["tenant"]["code"], "pas")

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse("auth-login"),
            {
                "username": "miguel",
                "password": "wrong-pass",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_logout_clears_session(self):
        self.client.login(username="miguel", password="test-pass")

        logout_response = self.client.post(reverse("auth-logout"))
        me_response = self.client.get(reverse("current-user"))

        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(me_response.status_code, 403)
