ASTDB_SCHEDULE_FAMILY = "horario"


def format_ranges_for_astdb(ranges):
    formatted_ranges = []

    for time_range in ranges:
        start = time_range.get("start")
        end = time_range.get("end")

        if not start or not end:
            raise ValueError("Cada rango debe tener start y end.")

        formatted_ranges.append(f"{start}-{end}")

    return "|".join(formatted_ranges)


def build_schedule_astdb_path(astdb_family, day_of_week):
    if not astdb_family:
        raise ValueError("astdb_family es obligatorio.")

    if not day_of_week:
        raise ValueError("day_of_week es obligatorio.")

    return f"/{ASTDB_SCHEDULE_FAMILY}/{astdb_family}/{day_of_week}"


def build_schedule_astdb_key(astdb_family, day_of_week):
    if not astdb_family:
        raise ValueError("astdb_family es obligatorio.")

    if not day_of_week:
        raise ValueError("day_of_week es obligatorio.")

    return f"{astdb_family}/{day_of_week}"


def build_schedule_astdb_value(schedule_day):
    return format_ranges_for_astdb(schedule_day.ranges)
