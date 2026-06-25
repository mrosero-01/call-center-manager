from django.contrib import admin

from .models import (
    CallCenterLocation,
    OperationSchedule,
    OperationScheduleDay,
    ScheduleChangeLog,
    ScheduleSyncJob,
    Tenant,
    TenantMembership,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code")
    search_fields = ("name", "code")


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "tenant", "role", "is_active")
    list_filter = ("tenant", "role", "is_active")
    search_fields = ("user__username", "tenant__name", "tenant__code")


@admin.register(CallCenterLocation)
class CallCenterLocationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "tenant", "astdb_family")
    list_filter = ("tenant",)
    search_fields = ("name", "code", "astdb_family", "tenant__name", "tenant__code")


class OperationScheduleDayInline(admin.TabularInline):
    model = OperationScheduleDay
    extra = 0


@admin.register(OperationSchedule)
class OperationScheduleAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "tenant", "timezone", "sync_status", "updated_at")
    list_filter = ("tenant", "timezone", "sync_status")
    search_fields = ("location__name", "location__code", "location__astdb_family")
    readonly_fields = ("sync_status", "last_sync_error", "last_synced_at")
    inlines = [OperationScheduleDayInline]


@admin.register(OperationScheduleDay)
class OperationScheduleDayAdmin(admin.ModelAdmin):
    list_display = ("id", "schedule", "day_of_week", "ranges")
    list_filter = ("day_of_week",)
    search_fields = ("schedule__location__name", "schedule__location__astdb_family")


@admin.register(ScheduleChangeLog)
class ScheduleChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "tenant", "changed_by", "created_at")
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

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScheduleSyncJob)
class ScheduleSyncJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "location",
        "tenant",
        "status",
        "attempts",
        "requested_by",
        "created_at",
        "synced_at",
    )
    list_filter = ("tenant", "status", "created_at")
    search_fields = ("location__name", "location__astdb_family", "reason", "last_error")
    readonly_fields = (
        "tenant",
        "location",
        "schedule",
        "change_log",
        "requested_by",
        "reason",
        "payload",
        "status",
        "attempts",
        "last_error",
        "synced_at",
        "created_at",
        "updated_at",
    )

    def has_delete_permission(self, request, obj=None):
        return False
