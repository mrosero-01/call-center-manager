import re

from ...application.schedule_rules import VALID_WEEKDAYS, parse_astdb_ranges


ASTDB_SCHEDULE_ROW_PATTERN = re.compile(
    r"(?:Output:\s*)?/horario/(?P<family>[^/\s:]+)/(?P<day>[^/\s:]+)\s*:\s*(?P<value>.*)"
)


def parse_astdb_schedule_rows(output):
    rows = []

    for line in output.splitlines():
        match = ASTDB_SCHEDULE_ROW_PATTERN.search(line)
        if not match:
            continue

        day_of_week = match.group("day")
        if day_of_week not in VALID_WEEKDAYS:
            continue

        rows.append(
            {
                "astdb_family": match.group("family"),
                "day_of_week": day_of_week,
                "ranges": parse_astdb_ranges(match.group("value").strip()),
            }
        )

    return rows
