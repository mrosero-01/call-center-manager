from types import SimpleNamespace

from django.test import SimpleTestCase

from .application.commands import ScheduleDayInput, UpdateOperationScheduleCommand
from .application.use_cases import UpdateOperationSchedule
from .infrastructure.asterisk.schedule_formatter import (
    build_schedule_astdb_key,
    build_schedule_astdb_path,
    build_schedule_astdb_value,
    format_ranges_for_astdb,
)
from .infrastructure.asterisk.schedule_publisher import AmiSchedulePublisher


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
