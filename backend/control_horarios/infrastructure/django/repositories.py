from django.db import transaction

from ...models import (
    CallCenterLocation,
    OperationSchedule,
    OperationScheduleDay,
    ScheduleChangeLog,
)


class DjangoScheduleRepository:
    """Adaptador de persistencia de horarios usando Django ORM."""

    def get_location_astdb_family(self, tenant_id, location_id):
        location = self._get_location(tenant_id, location_id)

        return location.astdb_family

    def get_schedule_snapshot(self, tenant_id, location_id):
        try:
            schedule = OperationSchedule.objects.prefetch_related("days").get(
                tenant_id=tenant_id,
                location_id=location_id,
            )
        except OperationSchedule.DoesNotExist:
            return {
                "timezone": None,
                "days": {},
            }

        return self._build_schedule_snapshot(schedule)

    @transaction.atomic
    def save_schedule(self, tenant_id, location_id, timezone, days):
        location = self._get_location(tenant_id, location_id)
        schedule, _created = OperationSchedule.objects.update_or_create(
            tenant_id=tenant_id,
            location=location,
            defaults={"timezone": timezone},
        )
        received_days = []

        for day in days:
            received_days.append(day.day_of_week)
            OperationScheduleDay.objects.update_or_create(
                schedule=schedule,
                day_of_week=day.day_of_week,
                defaults={"ranges": list(day.ranges)},
            )

        schedule.days.exclude(day_of_week__in=received_days).delete()
        schedule.refresh_from_db()

        return self._build_schedule_snapshot(schedule)

    def save_change_log(
        self,
        tenant_id,
        location_id,
        changed_by_id,
        reason,
        before_value,
        after_value,
    ):
        location = self._get_location(tenant_id, location_id)
        ScheduleChangeLog.objects.create(
            tenant_id=tenant_id,
            location=location,
            changed_by_id=changed_by_id,
            reason=reason,
            before_value=before_value,
            after_value=after_value,
        )

    def _get_location(self, tenant_id, location_id):
        return CallCenterLocation.objects.get(
            id=location_id,
            tenant_id=tenant_id,
        )

    def _build_schedule_snapshot(self, schedule):
        schedule_days = schedule.days.all()

        return {
            "timezone": schedule.timezone,
            "days": {
                schedule_day.day_of_week: schedule_day.ranges
                for schedule_day in schedule_days
            },
        }
