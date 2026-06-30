import re
import time
from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from control_horarios.infrastructure.asterisk.ami_client import SocketAmiClient
from control_horarios.infrastructure.asterisk.astdb_importer import (
    parse_astdb_schedule_rows,
)
from control_horarios.application.schedule_rules import VALID_WEEKDAYS
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
WEEKDAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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


def check_asterisk_health(client=None):
    client = client or build_ami_client()
    started_at = time.monotonic()
    output = client.command("core show uptime")
    elapsed_ms = round((time.monotonic() - started_at) * 1000)

    return {
        "ok": True,
        "host": settings.ASTERISK_AMI_HOST,
        "port": settings.ASTERISK_AMI_PORT,
        "latency_ms": elapsed_ms,
        "message": _first_meaningful_output_line(output) or "AMI respondio correctamente.",
    }


def inspect_asterisk_inventory(client=None):
    result = inspect_asterisk(client=client)
    contexts = set(result["contexts"])
    families = result["families"]
    names = sorted(contexts | set(families.keys()))
    locations = {
        location.astdb_family: location
        for location in CallCenterLocation.objects.filter(astdb_family__in=names)
        .select_related("tenant")
    }

    items = []
    for name in names:
        location = locations.get(name)
        days = families.get(name, [])
        items.append(
            {
                "name": name,
                "has_context": name in contexts,
                "has_astdb_schedule": bool(days),
                "days": days,
                "django_location": _serialize_location(location),
                "suggested_action": _suggest_inventory_action(
                    location=location,
                    has_astdb_schedule=bool(days),
                ),
            }
        )

    return items


def compare_location_schedule_with_astdb(location, client=None):
    asterisk_rows = read_astdb_schedule_rows(
        family=location.astdb_family,
        client=client,
    )
    asterisk_days = {
        row["day_of_week"]: row["ranges"]
        for row in asterisk_rows
    }
    django_days = _read_django_days(location)
    differences = []

    for day in WEEKDAY_ORDER:
        django_ranges = django_days.get(day, [])
        asterisk_ranges = asterisk_days.get(day, [])

        if django_ranges != asterisk_ranges:
            differences.append(
                {
                    "day_of_week": day,
                    "django_ranges": django_ranges,
                    "asterisk_ranges": asterisk_ranges,
                }
            )

    return {
        "astdb_family": location.astdb_family,
        "in_sync": len(differences) == 0,
        "django_days": django_days,
        "asterisk_days": asterisk_days,
        "differences": differences,
        "checked_at": timezone.now().isoformat(),
    }


def build_astdb_import_preview(tenant_code, tenant_name="", family="", client=None):
    rows = read_astdb_schedule_rows(family=family, client=client)
    return _build_import_preview_from_rows(
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        rows=rows,
    )


def build_selected_astdb_import_preview(
    tenant_code,
    tenant_name="",
    families=None,
    client=None,
):
    families = families or []
    rows = read_astdb_schedule_rows(client=client)
    selected_rows = [
        row for row in rows if not families or row["astdb_family"] in families
    ]

    return _build_import_preview_from_rows(
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        rows=selected_rows,
    )


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
    return _import_from_preview(
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        preview=preview,
    )


@transaction.atomic
def import_selected_astdb_schedules(
    tenant_code,
    tenant_name="",
    families=None,
    client=None,
):
    preview = build_selected_astdb_import_preview(
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        families=families or [],
        client=client,
    )

    return _import_from_preview(
        tenant_code=tenant_code,
        tenant_name=tenant_name,
        preview=preview,
    )


@transaction.atomic
def refresh_location_schedule_from_astdb(location, client=None):
    rows = read_astdb_schedule_rows(family=location.astdb_family, client=client)
    schedule, _created = OperationSchedule.objects.update_or_create(
        tenant=location.tenant,
        location=location,
        defaults={
            "timezone": settings.TIME_ZONE,
            "sync_status": OperationSchedule.SyncStatus.SYNCED,
            "last_sync_error": "",
            "last_synced_at": timezone.now(),
        },
    )
    imported_day_names = [row["day_of_week"] for row in rows]
    schedule.days.exclude(day_of_week__in=imported_day_names).delete()

    for row in rows:
        OperationScheduleDay.objects.update_or_create(
            schedule=schedule,
            day_of_week=row["day_of_week"],
            defaults={"ranges": row["ranges"]},
        )

    schedule.refresh_from_db()

    return schedule


def _build_import_preview_from_rows(tenant_code, tenant_name, rows):
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
                "is_active": (
                    existing_locations[astdb_family].is_active
                    if astdb_family in existing_locations
                    else False
                ),
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


def _import_from_preview(tenant_code, tenant_name, preview):
    tenant, _created = Tenant.objects.get_or_create(
        code=tenant_code,
        defaults={"name": tenant_name or tenant_code.upper()},
    )
    imported_days = 0
    imported_locations = []
    created_count = 0
    updated_count = 0
    restored_count = 0

    for location_plan in preview["locations"]:
        astdb_family = location_plan["astdb_family"]
        location, created = CallCenterLocation.objects.get_or_create(
            astdb_family=astdb_family,
            defaults={
                "tenant": tenant,
                "name": location_plan["name"],
                "code": astdb_family,
                "is_active": True,
            },
        )
        if created:
            created_count += 1
        elif not location.is_active:
            restored_count += 1
        else:
            updated_count += 1

        if not location.is_active:
            location.is_active = True
            location.save(update_fields=["is_active"])

        schedule, _created = OperationSchedule.objects.update_or_create(
            tenant=location.tenant,
            location=location,
            defaults={
                "timezone": settings.TIME_ZONE,
                "sync_status": OperationSchedule.SyncStatus.SYNCED,
                "last_sync_error": "",
                "last_synced_at": timezone.now(),
            },
        )
        imported_day_names = [row["day_of_week"] for row in location_plan["days"]]
        schedule.days.exclude(day_of_week__in=imported_day_names).delete()

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
        "created_count": created_count,
        "updated_count": updated_count,
        "restored_count": restored_count,
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


def _read_django_days(location):
    try:
        schedule = location.operation_schedule
    except OperationSchedule.DoesNotExist:
        return {}

    return {
        day.day_of_week: day.ranges
        for day in schedule.days.all()
    }


def _first_meaningful_output_line(output):
    for line in output.splitlines():
        normalized = line.replace("Output:", "").strip()
        if normalized and not normalized.startswith("Response:"):
            return normalized

    return ""


def _serialize_location(location):
    if not location:
        return None

    return {
        "id": location.id,
        "name": location.name,
        "code": location.code,
        "astdb_family": location.astdb_family,
        "tenant": location.tenant.code,
        "is_active": location.is_active,
    }


def _suggest_inventory_action(location, has_astdb_schedule):
    if location and not location.is_active:
        return "restore"

    if location and has_astdb_schedule:
        return "update"

    if location:
        return "created"

    if has_astdb_schedule:
        return "import"

    return "create"
