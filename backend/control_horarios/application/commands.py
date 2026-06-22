from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ScheduleDayInput:
    day_of_week: str
    ranges: Sequence[dict]


@dataclass(frozen=True)
class UpdateOperationScheduleCommand:
    tenant_id: int
    location_id: int
    changed_by_id: int
    reason: str
    timezone: str
    days: Sequence[ScheduleDayInput]
