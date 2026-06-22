from types import SimpleNamespace

from django.test import SimpleTestCase

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
