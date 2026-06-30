from rest_framework import serializers

from .application.schedule_rules import normalize_ranges
from .models import ScheduleChangeLog, ScheduleSyncJob, Tenant, TenantMembership
from .models import OperationScheduleDay
from .models import CallCenterLocation


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(
        max_length=128,
        trim_whitespace=False,
        write_only=True,
    )


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ("id", "name", "code")


class AdminTenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ("id", "name", "code")


class AdminCallCenterLocationSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer(read_only=True)
    tenant_id = serializers.PrimaryKeyRelatedField(
        queryset=Tenant.objects.all(),
        source="tenant",
        write_only=True,
    )

    class Meta:
        model = CallCenterLocation
        fields = ("id", "tenant", "tenant_id", "name", "code", "astdb_family", "is_active")


class TenantMembershipSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer()

    class Meta:
        model = TenantMembership
        fields = ("tenant", "role")


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    is_superuser = serializers.BooleanField()
    memberships = TenantMembershipSerializer(many=True)


class CallCenterLocationSerializer(serializers.ModelSerializer):
    tenant = serializers.CharField(source="tenant.code")

    class Meta:
        model = CallCenterLocation
        fields = ("id", "name", "code", "astdb_family", "tenant", "is_active")


class ScheduleChangeLogSerializer(serializers.ModelSerializer):
    changed_by = serializers.CharField(source="changed_by.username", allow_null=True)

    class Meta:
        model = ScheduleChangeLog
        fields = (
            "id",
            "changed_by",
            "reason",
            "before_value",
            "after_value",
            "created_at",
        )


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
    expected_updated_at = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(
        allow_blank=False,
        max_length=250,
        min_length=8,
        trim_whitespace=True,
    )
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


class OperationSchedulePreviewSerializer(serializers.Serializer):
    timezone = serializers.CharField(default="America/Bogota")
    days = ScheduleDaySerializer(many=True, allow_empty=False)

    def validate_days(self, days):
        return UpdateOperationScheduleSerializer().validate_days(days)


class AsteriskImportRequestSerializer(serializers.Serializer):
    tenant_code = serializers.SlugField(max_length=100)
    tenant_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    family = serializers.SlugField(
        max_length=100,
        required=False,
        allow_blank=True,
    )


class AsteriskImportSelectedRequestSerializer(serializers.Serializer):
    tenant_code = serializers.SlugField(max_length=100)
    tenant_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    families = serializers.ListField(
        child=serializers.SlugField(max_length=100),
        allow_empty=False,
        max_length=100,
    )


class ProcessSyncJobsSerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)
    retry_failed = serializers.BooleanField(default=False)
    max_attempts = serializers.IntegerField(min_value=1, max_value=20, default=5)


class ScheduleSyncJobSerializer(serializers.ModelSerializer):
    tenant = serializers.CharField(source="tenant.code")
    location = serializers.CharField(source="location.name")
    astdb_family = serializers.CharField(source="location.astdb_family")
    requested_by = serializers.CharField(source="requested_by.username", allow_null=True)

    class Meta:
        model = ScheduleSyncJob
        fields = (
            "id",
            "tenant",
            "location",
            "astdb_family",
            "requested_by",
            "reason",
            "status",
            "attempts",
            "last_error",
            "synced_at",
            "created_at",
            "updated_at",
        )
