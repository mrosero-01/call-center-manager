from .schedule_formatter import (
    ASTDB_SCHEDULE_FAMILY,
    build_schedule_astdb_key,
    format_ranges_for_astdb,
)


class AmiSchedulePublisher:
    """Adaptador de salida que publica horarios en AstDB mediante AMI."""

    def __init__(self, ami_client):
        self.ami_client = ami_client

    def publish_day(self, astdb_family, day_of_week, ranges):
        key = build_schedule_astdb_key(astdb_family, day_of_week)
        value = format_ranges_for_astdb(ranges)

        self.ami_client.db_put(
            family=ASTDB_SCHEDULE_FAMILY,
            key=key,
            value=value,
        )


class NoOpSchedulePublisher:
    """Publicador temporal para probar la API sin conectar AMI."""

    def publish_day(self, astdb_family, day_of_week, ranges):
        return None
