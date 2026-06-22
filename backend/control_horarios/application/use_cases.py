from typing import Sequence

from .commands import ScheduleDayInput, UpdateOperationScheduleCommand
from .ports import SchedulePublisher, ScheduleRepository


class UpdateOperationSchedule:
    """Caso de uso para cambiar el horario operativo de un lugar."""

    def __init__(
        self,
        repository: ScheduleRepository,
        publisher: SchedulePublisher,
    ):
        self.repository = repository
        self.publisher = publisher

    def execute(self, command: UpdateOperationScheduleCommand) -> dict:
        reason = command.reason.strip()
        self._validate_reason(reason)
        self._validate_days(command.days)

        before_value = self.repository.get_schedule_snapshot(
            tenant_id=command.tenant_id,
            location_id=command.location_id,
        )
        after_value = self.repository.save_schedule(
            tenant_id=command.tenant_id,
            location_id=command.location_id,
            timezone=command.timezone,
            days=command.days,
        )
        self.repository.save_change_log(
            tenant_id=command.tenant_id,
            location_id=command.location_id,
            changed_by_id=command.changed_by_id,
            reason=reason,
            before_value=before_value,
            after_value=after_value,
        )

        astdb_family = self.repository.get_location_astdb_family(
            tenant_id=command.tenant_id,
            location_id=command.location_id,
        )
        for day in command.days:
            self.publisher.publish_day(
                astdb_family=astdb_family,
                day_of_week=day.day_of_week,
                ranges=day.ranges,
            )

        return after_value

    def _validate_reason(self, reason: str) -> None:
        if not reason:
            raise ValueError("El motivo del cambio es obligatorio.")

    def _validate_days(self, days: Sequence[ScheduleDayInput]) -> None:
        if not days:
            raise ValueError("Debe enviar al menos un dia de horario.")

        for day in days:
            if not day.day_of_week:
                raise ValueError("Cada dia debe tener day_of_week.")

            for time_range in day.ranges:
                start = time_range.get("start")
                end = time_range.get("end")

                if not start or not end:
                    raise ValueError("Cada rango debe tener start y end.")

                if start >= end:
                    raise ValueError("El inicio del rango debe ser menor al fin.")
