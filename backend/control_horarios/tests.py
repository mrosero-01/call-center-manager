from types import SimpleNamespace

from django.test import SimpleTestCase

from .infrastructure.asterisk.schedule_formatter import (
    build_schedule_astdb_path,
    build_schedule_astdb_value,
    format_ranges_for_astdb,
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

    def test_builds_astdb_value_from_schedule_day(self):
        schedule_day = SimpleNamespace(
            ranges=[
                {"start": "08:00", "end": "12:00"},
                {"start": "14:00", "end": "23:59"},
            ]
        )

        value = build_schedule_astdb_value(schedule_day)

        self.assertEqual(value, "08:00-12:00|14:00-23:59")
