from rest_framework import serializers

from .application.schedule_rules import normalize_ranges
from .models import OperationScheduleDay
from .models import CallCenterLocation


class CallCenterLocationSerializer(serializers.ModelSerializer):
    tenant = serializers.CharField(source="tenant.code")

    class Meta:
        model = CallCenterLocation
        fields = ("id", "name", "code", "astdb_family", "tenant")


class ScheduleRangeSerializer(serializers.Serializer):
    start = serializers.RegexField(regex=r"^([01]\d|2[0-3]):[0-5]\d$")
    end = serializers.RegexField(regex=r"^([01]\d|2[0-3]):[0-5]\d$")

    def validate(self, attrs):
        if attrs["start"] >= attrs["end"]:
            raise serializers.ValidationError("El inicio debe ser menor al fin.")

        return attrs


class ScheduleDaySerializer(serializers.Serializer):
    day_of_week = serializers.ChoiceField(choices=OperationScheduleDay.Weekday.choices)
    ranges = ScheduleRangeSerializer(many=True, allow_empty=True)

    def validate_ranges(self, ranges):
        try:
            return normalize_ranges(ranges)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class UpdateOperationScheduleSerializer(serializers.Serializer):
    timezone = serializers.CharField(default="America/Bogota")
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)
    days = ScheduleDaySerializer(many=True, allow_empty=False)

    def validate_days(self, days):
        seen_days = set()

        for day in days:
            day_of_week = day["day_of_week"]

            if day_of_week in seen_days:
                raise serializers.ValidationError(
                    f"El dia {day_of_week} esta repetido."
                )

            seen_days.add(day_of_week)

        return days
