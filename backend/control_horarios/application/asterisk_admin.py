import re
from collections import defaultdict

from django.conf import settings
from django.db import transaction

from control_horarios.infrastructure.asterisk.ami_client import SocketAmiClient
from control_horarios.infrastructure.asterisk.astdb_importer import (
    parse_astdb_schedule_rows,
)
from control_horarios.models import (
    CallCenterLocation,
    OperationSchedule,
    OperationScheduleDay,
    Tenant,
)


DIALPLAN_CONTEXT_PATTERN = re.compile(
    r"^(?:Output:\s*)?\[ Context '([^']+)'",
    re.MULTILINE,
)


def build_ami_client():
    return SocketAmiClient(
        host=settings.ASTERISK_AMI_HOST,
        port=settings.ASTERISK_AMI_PORT,
        username=settings.ASTERISK_AMI_USERNAME,
        password=settings.ASTERISK_AMI_PASSWORD,
        timeout=settings.ASTERISK_AMI_TIMEOUT,
    )


def inspect_asterisk(client=None):
    client = client or build_ami_client()
    astdb_output = client.command("database show horario")
    dialplan_output = client.command("dialplan show")
    rows = parse_astdb_schedule_rows(astdb_output)
    contexts = sorted(set(DIALPLAN_CONTEXT_PATTERN.findall(dialplan_output)))

    return {
        "contexts": contexts,
        "families": _group_rows_by_family(rows),
        "raw_horario": astdb_output,
    }


def build_astdb_import_preview(tenant_code, tenant_name="", family="", client=None):
    rows = read_astdb_schedule_rows(family=family, client=client)
    grouped_rows = _group_rows_by_family(rows)
    existing_locations = {
        location.astdb_family: location
        for location in CallCenterLocation.objects.filter(
            astdb_family__in=grouped_rows.keys()
        ).select_related("tenant")
    }

    return {
        "tenant": {
            "code": tenant_code,
            "name": tenant_name or tenant_code.upper(),
        },
        "locations": [
            {
                "astdb_family": astdb_family,
                "name": _humanize_family(astdb_family),
                "exists": astdb_family in existing_locations,
                "current_tenant": (
                    existing_locations[astdb_family].tenant.code
                    if astdb_family in existing_locations
                    else ""
                ),
                "days": rows,
            }
            for astdb_family, rows in grouped_rows.items()
        ],
    }


def read_astdb_schedule_rows(family="", client=None):
    client = client or build_ami_client()
    output = client.command("database show horario")
    rows = parse_astdb_schedule_rows(output)

    if family:
        rows = [row for row in rows if row["astdb_family"] == family]

    return rows


@transaction.atomic
def import_astdb_schedules(tenant_code, tenant_name="", family="", client=None):
    preview = build_astdb_import_preview(
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        family=family,
        client=client,
    )
    tenant, _created = Tenant.objects.get_or_create(
        code=tenant_code,
        defaults={"name": tenant_name or tenant_code.upper()},
    )
    imported_days = 0
    imported_locations = []

    for location_plan in preview["locations"]:
        astdb_family = location_plan["astdb_family"]
        location, _created = CallCenterLocation.objects.get_or_create(
            astdb_family=astdb_family,
            defaults={
                "tenant": tenant,
                "name": location_plan["name"],
                "code": astdb_family,
            },
        )
        schedule, _created = OperationSchedule.objects.update_or_create(
            tenant=location.tenant,
            location=location,
            defaults={"timezone": settings.TIME_ZONE},
        )

        for row in location_plan["days"]:
            OperationScheduleDay.objects.update_or_create(
                schedule=schedule,
                day_of_week=row["day_of_week"],
                defaults={"ranges": row["ranges"]},
            )
            imported_days += 1

        imported_locations.append(location)

    return {
        "tenant": tenant,
        "locations": imported_locations,
        "imported_days": imported_days,
    }


def _group_rows_by_family(rows):
    grouped_rows = defaultdict(list)

    for row in rows:
        grouped_rows[row["astdb_family"]].append(
            {
                "day_of_week": row["day_of_week"],
                "ranges": row["ranges"],
            }
        )

    return dict(sorted(grouped_rows.items()))


def _humanize_family(astdb_family):
    return astdb_family.replace("_", " ").title()
