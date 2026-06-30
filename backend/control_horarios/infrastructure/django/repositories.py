from django.db import transaction

from ...models import (
    CallCenterLocation,
    OperationSchedule,
    OperationScheduleDay,
    ScheduleChangeLog,
    ScheduleSyncJob,
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
                "updated_at": None,
                "days": {},
            }

        return self._build_schedule_snapshot(schedule)

    @transaction.atomic
    def save_schedule(self, tenant_id, location_id, timezone, days):
        location = self._get_location(tenant_id, location_id)
        schedule, _created = OperationSchedule.objects.update_or_create(
            tenant_id=tenant_id,
            location=location,
            defaults={
                "timezone": timezone,
                "sync_status": OperationSchedule.SyncStatus.PENDING,
                "last_sync_error": "",
            },
        )
        for day in days:
            OperationScheduleDay.objects.update_or_create(
                schedule=schedule,
                day_of_week=day.day_of_week,
                defaults={"ranges": list(day.ranges)},
            )

        schedule.refresh_from_db()

        return self._build_schedule_snapshot(schedule)

    @transaction.atomic
    def save_schedule_change(
        self,
        tenant_id,
        location_id,
        changed_by_id,
        reason,
        timezone,
        days,
    ):
        before_value = self.get_schedule_snapshot(
            tenant_id=tenant_id,
            location_id=location_id,
        )
        after_value = self.save_schedule(
            tenant_id=tenant_id,
            location_id=location_id,
            timezone=timezone,
            days=days,
        )
        change_log = self.save_change_log(
            tenant_id=tenant_id,
            location_id=location_id,
            changed_by_id=changed_by_id,
            reason=reason,
            before_value=before_value,
            after_value=after_value,
        )
        sync_job = self.create_sync_job(
            tenant_id=tenant_id,
            location_id=location_id,
            changed_by_id=changed_by_id,
            reason=reason,
            timezone=timezone,
            days=days,
            change_log_id=change_log.id,
        )
        after_value["sync_job_id"] = sync_job.id

        return after_value

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
        return ScheduleChangeLog.objects.create(
            tenant_id=tenant_id,
            location=location,
            changed_by_id=changed_by_id,
            reason=reason,
            before_value=before_value,
            after_value=after_value,
        )

    def create_sync_job(
        self,
        tenant_id,
        location_id,
        changed_by_id,
        reason,
        timezone,
        days,
        change_log_id=None,
    ):
        location = self._get_location(tenant_id, location_id)
        schedule = OperationSchedule.objects.get(
            tenant_id=tenant_id,
            location=location,
        )

        return ScheduleSyncJob.objects.create(
            tenant_id=tenant_id,
            location=location,
            schedule=schedule,
            change_log_id=change_log_id,
            requested_by_id=changed_by_id,
            reason=reason,
            payload={
                "timezone": timezone,
                "days": [
                    {
                        "day_of_week": day.day_of_week,
                        "ranges": list(day.ranges),
                    }
                    for day in days
                ],
            },
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
            "sync_status": schedule.sync_status,
            "last_sync_error": schedule.last_sync_error,
            "last_synced_at": schedule.last_synced_at.isoformat()
            if schedule.last_synced_at
            else None,
            "updated_at": schedule.updated_at.isoformat()
            if schedule.updated_at
            else None,
            "days": {
                schedule_day.day_of_week: schedule_day.ranges
                for schedule_day in schedule_days
            },
        }
