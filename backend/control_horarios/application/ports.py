from typing import Protocol, Sequence


class SchedulePublisher(Protocol):
    """Puerto de salida para publicar horarios fuera de la aplicacion."""

    def publish_day(
        self,
        astdb_family: str,
        day_of_week: str,
        ranges: Sequence[dict],
    ) -> None:
        pass
