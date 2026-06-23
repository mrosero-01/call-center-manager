VALID_WEEKDAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}


def normalize_ranges(ranges):
    normalized_ranges = [
        {
            "start": time_range["start"],
            "end": time_range["end"],
        }
        for time_range in ranges
    ]
    normalized_ranges.sort(key=lambda time_range: time_range["start"])
    _validate_no_overlaps(normalized_ranges)

    return normalized_ranges


def normalize_days(days):
    return [
        {
            "day_of_week": day["day_of_week"],
            "ranges": normalize_ranges(day["ranges"]),
        }
        for day in days
    ]


def parse_astdb_ranges(value):
    if not value:
        return []

    ranges = []
    for raw_range in value.split("|"):
        if "-" not in raw_range:
            raise ValueError(f"Rango invalido en AstDB: {raw_range}")

        start, end = raw_range.split("-", maxsplit=1)
        ranges.append(
            {
                "start": start.strip(),
                "end": end.strip(),
            }
        )

    return normalize_ranges(ranges)


def _validate_no_overlaps(ranges):
    previous_range = None

    for current_range in ranges:
        if previous_range and current_range["start"] < previous_range["end"]:
            raise ValueError("Las franjas horarias no pueden solaparse.")

        previous_range = current_range
