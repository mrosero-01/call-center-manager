from typing import Sequence

from .commands import ScheduleDayInput, UpdateOperationScheduleCommand
from .ports import ScheduleRepository
from .schedule_rules import normalize_ranges


class UpdateOperationSchedule:
    """Caso de uso para cambiar el horario operativo de un lugar."""

    def __init__(
        self,
        repository: ScheduleRepository,
    ):
        self.repository = repository

    def execute(self, command: UpdateOperationScheduleCommand) -> dict:
        reason = command.reason.strip()
        self._validate_reason(reason)
        days = self._normalize_days(command.days)

        return self.repository.save_schedule_change(
            tenant_id=command.tenant_id,
            location_id=command.location_id,
            changed_by_id=command.changed_by_id,
            reason=reason,
            timezone=command.timezone,
            days=days,
        )

    def _validate_reason(self, reason: str) -> None:
        if not reason:
            raise ValueError("El motivo del cambio es obligatorio.")

        if len(reason) < 8:
            raise ValueError("El motivo debe tener al menos 8 caracteres.")

        if len(reason) > 250:
            raise ValueError("El motivo no puede superar 250 caracteres.")

    def _normalize_days(self, days: Sequence[ScheduleDayInput]) -> list[ScheduleDayInput]:
        if not days:
            raise ValueError("Debe enviar al menos un dia de horario.")

        normalized_days = []
        seen_days = set()
        for day in days:
            if not day.day_of_week:
                raise ValueError("Cada dia debe tener day_of_week.")

            if day.day_of_week in seen_days:
                raise ValueError("No puede enviar el mismo dia mas de una vez.")

            seen_days.add(day.day_of_week)

            for time_range in day.ranges:
                start = time_range.get("start")
                end = time_range.get("end")

                if not start or not end:
                    raise ValueError("Cada rango debe tener start y end.")

            normalized_days.append(
                ScheduleDayInput(
                    day_of_week=day.day_of_week,
                    ranges=normalize_ranges(day.ranges),
                )
            )

        return normalized_days
