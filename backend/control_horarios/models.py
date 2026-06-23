from django.conf import settings
from django.db import models


class Tenant(models.Model):
    """Contratista o cliente dueño de una configuración de call center."""

    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TenantMembership(models.Model):
    """Relacion entre un usuario de Django y un contratista."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        OPERATOR = "operator", "Operador"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tenant_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.OPERATOR,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tenant__name", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user"],
                name="unique_user_membership_per_tenant",
            ),
        ]

    def __str__(self):
        return f"{self.user} en {self.tenant}"


class CallCenterLocation(models.Model):
    """Lugar o unidad operativa del call center consultada por Asterisk."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="locations",
    )
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=100)
    astdb_family = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["tenant__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="unique_location_code_per_tenant",
            ),
        ]

    def __str__(self):
        return f"{self.tenant.code} / {self.name}"


class OperationSchedule(models.Model):
    """Horario vigente de operación para un lugar de call center."""

    class SyncStatus(models.TextChoices):
        PENDING = "pending", "Pendiente"
        SYNCED = "synced", "Sincronizado"
        FAILED = "failed", "Fallido"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="operation_schedules",
    )
    location = models.OneToOneField(
        CallCenterLocation,
        on_delete=models.PROTECT,
        related_name="operation_schedule",
    )
    timezone = models.CharField(max_length=64, default="America/Bogota")
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    last_sync_error = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant__name", "location__name"]

    def __str__(self):
        return f"Horario {self.location} ({self.timezone})"


class OperationScheduleDay(models.Model):
    """Rangos horarios de un dia especifico dentro de un horario."""

    class Weekday(models.TextChoices):
        MONDAY = "Mon", "Lunes"
        TUESDAY = "Tue", "Martes"
        WEDNESDAY = "Wed", "Miercoles"
        THURSDAY = "Thu", "Jueves"
        FRIDAY = "Fri", "Viernes"
        SATURDAY = "Sat", "Sabado"
        SUNDAY = "Sun", "Domingo"

    schedule = models.ForeignKey(
        OperationSchedule,
        on_delete=models.CASCADE,
        related_name="days",
    )
    day_of_week = models.CharField(max_length=3, choices=Weekday.choices)
    ranges = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["schedule", "day_of_week"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "day_of_week"],
                name="unique_day_per_schedule",
            ),
        ]

    def __str__(self):
        return f"{self.schedule.location} - {self.day_of_week}"


class ScheduleChangeLog(models.Model):
    """Auditoria de cambios realizados sobre el horario de un lugar."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="schedule_change_logs",
    )
    location = models.ForeignKey(
        CallCenterLocation,
        on_delete=models.PROTECT,
        related_name="schedule_change_logs",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="schedule_changes",
    )
    reason = models.TextField()
    before_value = models.JSONField(default=dict)
    after_value = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Cambio de horario en {self.location} por {self.changed_by}"


class ScheduleSyncJob(models.Model):
    """Trabajo pendiente para sincronizar un horario hacia Asterisk."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        SYNCED = "synced", "Sincronizado"
        FAILED = "failed", "Fallido"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="schedule_sync_jobs",
    )
    location = models.ForeignKey(
        CallCenterLocation,
        on_delete=models.PROTECT,
        related_name="schedule_sync_jobs",
    )
    schedule = models.ForeignKey(
        OperationSchedule,
        on_delete=models.CASCADE,
        related_name="sync_jobs",
    )
    change_log = models.ForeignKey(
        ScheduleChangeLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sync_jobs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="requested_schedule_sync_jobs",
    )
    reason = models.TextField()
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["location", "status"]),
        ]

    def __str__(self):
        return f"Sync {self.location} ({self.status})"
