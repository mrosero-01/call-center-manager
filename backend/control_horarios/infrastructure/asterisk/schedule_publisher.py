from .schedule_formatter import (
    ASTDB_SCHEDULE_FAMILY,
    build_schedule_astdb_key,
    format_ranges_for_astdb,
)


class AmiSchedulePublisher:
    """Adaptador de salida que publica horarios en AstDB mediante AMI."""

    def __init__(self, ami_client):
        self.ami_client = ami_client

    def publish_days(self, astdb_family, days):
        actions = []

        for day in days:
            key = build_schedule_astdb_key(astdb_family, day.day_of_week)

            if day.ranges:
                actions.append(
                    {
                        "fields": {
                            "Action": "DBPut",
                            "Family": ASTDB_SCHEDULE_FAMILY,
                            "Key": key,
                            "Val": format_ranges_for_astdb(day.ranges),
                        },
                        "error_message": "DBPut AMI fallido",
                    }
                )
            else:
                actions.append(
                    {
                        "fields": {
                            "Action": "DBDel",
                            "Family": ASTDB_SCHEDULE_FAMILY,
                            "Key": key,
                        },
                        "error_message": "DBDel AMI fallido",
                        "allow_missing": True,
                    }
                )

        if actions:
            self.ami_client.run_database_actions(actions)

    def publish_day(self, astdb_family, day_of_week, ranges):
        key = build_schedule_astdb_key(astdb_family, day_of_week)

        if ranges:
            self.ami_client.db_put(
                family=ASTDB_SCHEDULE_FAMILY,
                key=key,
                value=format_ranges_for_astdb(ranges),
            )
        else:
            self.ami_client.db_del(
                family=ASTDB_SCHEDULE_FAMILY,
                key=key,
            )


class NoOpSchedulePublisher:
    """Publicador temporal para probar la API sin conectar AMI."""

    def publish_days(self, astdb_family, days):
        return None

    def publish_day(self, astdb_family, day_of_week, ranges):
        return None
