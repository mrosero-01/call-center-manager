from typing import Protocol, Sequence

from .commands import ScheduleDayInput


class ScheduleRepository(Protocol):
    """Puerto de persistencia para horarios y auditoria."""

    def get_location_astdb_family(self, tenant_id: int, location_id: int) -> str:
        pass

    def get_schedule_snapshot(self, tenant_id: int, location_id: int) -> dict:
        pass

    def save_schedule(
        self,
        tenant_id: int,
        location_id: int,
        timezone: str,
        days: Sequence[ScheduleDayInput],
    ) -> dict:
        pass

    def save_schedule_change(
        self,
        tenant_id: int,
        location_id: int,
        changed_by_id: int,
        reason: str,
        timezone: str,
        days: Sequence[ScheduleDayInput],
    ) -> dict:
        pass

    def save_change_log(
        self,
        tenant_id: int,
        location_id: int,
        changed_by_id: int,
        reason: str,
        before_value: dict,
        after_value: dict,
    ) -> None:
        pass


class SchedulePublisher(Protocol):
    """Puerto de salida para publicar horarios fuera de la aplicacion."""

    def publish_days(
        self,
        astdb_family: str,
        days: Sequence[ScheduleDayInput],
    ) -> None:
        pass

    def publish_day(
        self,
        astdb_family: str,
        day_of_week: str,
        ranges: Sequence[dict],
    ) -> None:
        pass
