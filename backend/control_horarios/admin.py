from django.contrib import admin

from .models import (
    CallCenterLocation,
    OperationSchedule,
    OperationScheduleDay,
    ScheduleChangeLog,
    Tenant,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(CallCenterLocation)
class CallCenterLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "tenant", "astdb_family")
    list_filter = ("tenant",)
    search_fields = ("name", "code", "astdb_family", "tenant__name", "tenant__code")


class OperationScheduleDayInline(admin.TabularInline):
    model = OperationScheduleDay
    extra = 0


@admin.register(OperationSchedule)
class OperationScheduleAdmin(admin.ModelAdmin):
    list_display = ("location", "tenant", "timezone", "updated_at")
    list_filter = ("tenant", "timezone")
    search_fields = ("location__name", "location__code", "location__astdb_family")
    inlines = [OperationScheduleDayInline]


@admin.register(OperationScheduleDay)
class OperationScheduleDayAdmin(admin.ModelAdmin):
    list_display = ("schedule", "day_of_week", "ranges")
    list_filter = ("day_of_week",)
    search_fields = ("schedule__location__name", "schedule__location__astdb_family")


@admin.register(ScheduleChangeLog)
class ScheduleChangeLogAdmin(admin.ModelAdmin):
    list_display = ("location", "tenant", "changed_by", "created_at")
    list_filter = ("tenant", "created_at")
    search_fields = ("location__name", "location__astdb_family", "reason")
    readonly_fields = (
        "tenant",
        "location",
        "changed_by",
        "reason",
        "before_value",
        "after_value",
        "created_at",
    )
