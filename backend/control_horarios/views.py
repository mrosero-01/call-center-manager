from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.utils.decorators import method_decorator

from .application.asterisk_admin import (
    build_astdb_import_preview,
    build_selected_astdb_import_preview,
    check_asterisk_health,
    compare_location_schedule_with_astdb,
    import_astdb_schedules,
    import_selected_astdb_schedules,
    inspect_asterisk,
    inspect_asterisk_inventory,
    refresh_location_schedule_from_astdb,
)
from .application.commands import ScheduleDayInput, UpdateOperationScheduleCommand
from .application.sync_jobs import process_schedule_sync_jobs
from .application.sync_jobs import process_schedule_sync_job
from .application.use_cases import UpdateOperationSchedule
from .infrastructure.asterisk.ami_client import AmiClientError
from .infrastructure.asterisk.schedule_formatter import (
    ASTDB_SCHEDULE_FAMILY,
    build_schedule_astdb_key,
    build_schedule_astdb_path,
    format_ranges_for_astdb,
)
from .infrastructure.django.repositories import DjangoScheduleRepository
from .models import (
    CallCenterLocation,
    OperationSchedule,
    ScheduleChangeLog,
    ScheduleSyncJob,
    Tenant,
    TenantMembership,
)
from .permissions import (
    get_manageable_locations,
    user_can_manage_location,
    user_can_view_location,
)
from .serializers import (
    AdminCallCenterLocationSerializer,
    AdminTenantSerializer,
    AsteriskImportSelectedRequestSerializer,
    AsteriskImportRequestSerializer,
    CallCenterLocationSerializer,
    CurrentUserSerializer,
    LoginSerializer,
    OperationSchedulePreviewSerializer,
    ProcessSyncJobsSerializer,
    ScheduleChangeLogSerializer,
    ScheduleSyncJobSerializer,
    UpdateOperationScheduleSerializer,
)


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        if user is None:
            return Response(
                {"detail": "Credenciales invalidas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)

        return Response(_serialize_current_user(user), status=status.HTTP_200_OK)


@method_decorator(ensure_csrf_cookie, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class CsrfCookieView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"detail": "CSRF cookie set."}, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)

        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(never_cache, name="dispatch")
class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            _serialize_current_user(request.user),
            status=status.HTTP_200_OK,
        )


@method_decorator(never_cache, name="dispatch")
class CallCenterLocationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        locations = get_manageable_locations(request.user)
        serializer = CallCenterLocationSerializer(locations, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class OperationScheduleUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)

        if not user_can_view_location(request.user, location):
            return Response(
                {"detail": "No tienes permiso para ver este horario."},
                status=status.HTTP_403_FORBIDDEN,
            )

        snapshot = DjangoScheduleRepository().get_schedule_snapshot(
            tenant_id=location.tenant_id,
            location_id=location.id,
        )

        return Response(
            {
                "location": CallCenterLocationSerializer(location).data,
                "timezone": snapshot["timezone"],
                "sync_status": snapshot.get("sync_status"),
                "last_sync_error": snapshot.get("last_sync_error", ""),
                "last_synced_at": snapshot.get("last_synced_at"),
                "updated_at": snapshot.get("updated_at"),
                "days": snapshot["days"],
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)

        if not user_can_manage_location(request.user, location):
            return Response(
                {"detail": "No tienes permiso para modificar este horario."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UpdateOperationScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conflict_response = self._validate_expected_version(
            location=location,
            expected_updated_at=serializer.validated_data.get("expected_updated_at"),
        )

        if conflict_response:
            return conflict_response

        command = self._build_command(
            user_id=request.user.id,
            tenant_id=location.tenant_id,
            location_id=location.id,
            validated_data=serializer.validated_data,
        )
        use_case = UpdateOperationSchedule(
            repository=DjangoScheduleRepository(),
        )

        try:
            result = use_case.execute(command)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sync_job_id = result.pop("sync_job_id", None)
        if sync_job_id:
            sync_job = ScheduleSyncJob.objects.select_related(
                "location",
                "schedule",
            ).get(id=sync_job_id)
            process_schedule_sync_job(sync_job)
            result = DjangoScheduleRepository().get_schedule_snapshot(
                tenant_id=location.tenant_id,
                location_id=location.id,
            )

        return Response(result, status=status.HTTP_200_OK)

    def _validate_expected_version(self, location, expected_updated_at):
        if expected_updated_at is None:
            return None

        try:
            schedule = OperationSchedule.objects.get(location=location)
        except OperationSchedule.DoesNotExist:
            return None

        if schedule.updated_at == expected_updated_at:
            return None

        return Response(
            {
                "detail": "Este horario fue modificado por otra sesion. Refresca antes de guardar.",
                "current_updated_at": schedule.updated_at.isoformat(),
            },
            status=status.HTTP_409_CONFLICT,
        )

    def _build_command(self, user_id, tenant_id, location_id, validated_data):
        return UpdateOperationScheduleCommand(
            tenant_id=tenant_id,
            location_id=location_id,
            changed_by_id=user_id,
            reason=validated_data["reason"],
            timezone=validated_data["timezone"],
            days=[
                ScheduleDayInput(
                    day_of_week=day["day_of_week"],
                    ranges=day["ranges"],
                )
                for day in validated_data["days"]
            ],
        )


@method_decorator(never_cache, name="dispatch")
class OperationSchedulePreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)

        if not user_can_manage_location(request.user, location):
            return Response(
                {"detail": "No tienes permiso para previsualizar este horario."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OperationSchedulePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(
            {
                "location": CallCenterLocationSerializer(location).data,
                "astdb_family": location.astdb_family,
                "actions": [
                    self._build_preview_action(location.astdb_family, day)
                    for day in serializer.validated_data["days"]
                ],
            },
            status=status.HTTP_200_OK,
        )

    def _build_preview_action(self, astdb_family, day):
        day_of_week = day["day_of_week"]
        ranges = day["ranges"]
        action = {
            "day_of_week": day_of_week,
            "family": ASTDB_SCHEDULE_FAMILY,
            "key": build_schedule_astdb_key(astdb_family, day_of_week),
            "path": build_schedule_astdb_path(astdb_family, day_of_week),
            "ranges": ranges,
        }

        if ranges:
            action["action"] = "DBPut"
            action["value"] = format_ranges_for_astdb(ranges)
        else:
            action["action"] = "DBDel"
            action["value"] = ""

        return action


@method_decorator(never_cache, name="dispatch")
class OperationScheduleRefreshFromAsteriskView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)

        if not user_can_manage_location(request.user, location):
            return Response(
                {"detail": "No tienes permiso para refrescar este horario."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            refresh_location_schedule_from_astdb(location)
        except (AmiClientError, OSError) as exc:
            return Response(
                {"detail": f"No se pudo leer AstDB: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        snapshot = DjangoScheduleRepository().get_schedule_snapshot(
            tenant_id=location.tenant_id,
            location_id=location.id,
        )

        return Response(
            {
                "location": CallCenterLocationSerializer(location).data,
                "timezone": snapshot["timezone"],
                "sync_status": snapshot.get("sync_status"),
                "last_sync_error": snapshot.get("last_sync_error", ""),
                "last_synced_at": snapshot.get("last_synced_at"),
                "updated_at": snapshot.get("updated_at"),
                "days": snapshot["days"],
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(never_cache, name="dispatch")
class OperationScheduleAsteriskComparisonView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)

        if not user_can_view_location(request.user, location):
            return Response(
                {"detail": "No tienes permiso para comparar este horario."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            comparison = compare_location_schedule_with_astdb(location)
        except (AmiClientError, OSError, ValueError) as exc:
            return Response(
                {"detail": f"No se pudo comparar contra AstDB: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(comparison, status=status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class ScheduleChangeLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)

        if not user_can_view_location(request.user, location):
            return Response(
                {"detail": "No tienes permiso para ver esta auditoria."},
                status=status.HTTP_403_FORBIDDEN,
            )

        change_logs = ScheduleChangeLog.objects.select_related("changed_by").filter(
            location=location,
        )
        serializer = ScheduleChangeLogSerializer(change_logs, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class IsSuperUser(BasePermission):
    message = "Solo un superadmin puede usar esta funcion."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class SuperuserOnlyMixin:
    permission_classes = [IsAuthenticated, IsSuperUser]


@method_decorator(never_cache, name="dispatch")
class AdminTenantListCreateView(SuperuserOnlyMixin, APIView):
    def get(self, request):
        tenants = Tenant.objects.all()
        serializer = AdminTenantSerializer(tenants, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AdminTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()

        return Response(
            AdminTenantSerializer(tenant).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(never_cache, name="dispatch")
class AdminLocationListCreateView(SuperuserOnlyMixin, APIView):
    def get(self, request):
        locations = CallCenterLocation.objects.select_related("tenant").all()
        serializer = AdminCallCenterLocationSerializer(locations, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AdminCallCenterLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = serializer.save()

        return Response(
            AdminCallCenterLocationSerializer(location).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(never_cache, name="dispatch")
class AdminLocationArchiveView(SuperuserOnlyMixin, APIView):
    def post(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)
        location.is_active = False
        location.save(update_fields=["is_active"])

        return Response(
            AdminCallCenterLocationSerializer(location).data,
            status=status.HTTP_200_OK,
        )


@method_decorator(never_cache, name="dispatch")
class AdminLocationRestoreView(SuperuserOnlyMixin, APIView):
    def post(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)
        location.is_active = True
        location.save(update_fields=["is_active"])

        return Response(
            AdminCallCenterLocationSerializer(location).data,
            status=status.HTTP_200_OK,
        )


@method_decorator(never_cache, name="dispatch")
class AdminAsteriskInspectView(SuperuserOnlyMixin, APIView):
    def get(self, request):
        try:
            result = inspect_asterisk()
        except (AmiClientError, OSError) as exc:
            return Response(
                {"detail": f"No se pudo inspeccionar Asterisk: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "contexts": result["contexts"],
                "families": [
                    {
                        "astdb_family": astdb_family,
                        "days": days,
                    }
                    for astdb_family, days in result["families"].items()
                ],
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(never_cache, name="dispatch")
class AdminAsteriskInventoryView(SuperuserOnlyMixin, APIView):
    def get(self, request):
        try:
            inventory = inspect_asterisk_inventory()
        except (AmiClientError, OSError) as exc:
            return Response(
                {"detail": f"No se pudo inspeccionar Asterisk: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"items": inventory}, status=status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class AdminAsteriskHealthView(SuperuserOnlyMixin, APIView):
    def get(self, request):
        try:
            health = check_asterisk_health()
        except (AmiClientError, OSError) as exc:
            return Response(
                {
                    "ok": False,
                    "detail": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(health, status=status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class AdminAsteriskImportPreviewView(SuperuserOnlyMixin, APIView):
    def post(self, request):
        serializer = AsteriskImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            preview = build_astdb_import_preview(**serializer.validated_data)
        except (AmiClientError, OSError) as exc:
            return Response(
                {"detail": f"No se pudo leer AstDB: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(preview, status=status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class AdminAsteriskImportSelectedPreviewView(SuperuserOnlyMixin, APIView):
    def post(self, request):
        serializer = AsteriskImportSelectedRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            preview = build_selected_astdb_import_preview(**serializer.validated_data)
        except (AmiClientError, OSError) as exc:
            return Response(
                {"detail": f"No se pudo leer AstDB: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(preview, status=status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class AdminAsteriskImportView(SuperuserOnlyMixin, APIView):
    def post(self, request):
        serializer = AsteriskImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = import_astdb_schedules(**serializer.validated_data)
        except (AmiClientError, OSError) as exc:
            return Response(
                {"detail": f"No se pudo importar desde AstDB: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "tenant": AdminTenantSerializer(result["tenant"]).data,
                "locations": AdminCallCenterLocationSerializer(
                    result["locations"],
                    many=True,
                ).data,
                "imported_days": result["imported_days"],
                "created_count": result.get("created_count", 0),
                "updated_count": result.get("updated_count", 0),
                "restored_count": result.get("restored_count", 0),
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(never_cache, name="dispatch")
class AdminAsteriskImportSelectedView(SuperuserOnlyMixin, APIView):
    def post(self, request):
        serializer = AsteriskImportSelectedRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = import_selected_astdb_schedules(**serializer.validated_data)
        except (AmiClientError, OSError) as exc:
            return Response(
                {"detail": f"No se pudo importar desde AstDB: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "tenant": AdminTenantSerializer(result["tenant"]).data,
                "locations": AdminCallCenterLocationSerializer(
                    result["locations"],
                    many=True,
                ).data,
                "imported_days": result["imported_days"],
                "created_count": result.get("created_count", 0),
                "updated_count": result.get("updated_count", 0),
                "restored_count": result.get("restored_count", 0),
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(never_cache, name="dispatch")
class AdminScheduleSyncJobListView(SuperuserOnlyMixin, APIView):
    def get(self, request):
        jobs = ScheduleSyncJob.objects.select_related(
            "tenant",
            "location",
            "requested_by",
        ).order_by("-created_at")[:100]
        serializer = ScheduleSyncJobSerializer(jobs, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class AdminScheduleSyncJobProcessView(SuperuserOnlyMixin, APIView):
    def post(self, request):
        serializer = ProcessSyncJobsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = process_schedule_sync_jobs(**serializer.validated_data)

        return Response(
            {
                "processed": result["processed"],
                "synced": result["synced"],
                "failed": result["failed"],
                "failed_jobs": [
                    {
                        "id": failed_job["job"].id,
                        "error": failed_job["error"],
                    }
                    for failed_job in result["failed_jobs"]
                ],
            },
            status=status.HTTP_200_OK,
        )


def _serialize_current_user(user):
    memberships = TenantMembership.objects.select_related("tenant").filter(
        user=user,
        is_active=True,
    )
    serializer = CurrentUserSerializer(
        {
            "id": user.id,
            "username": user.username,
            "is_superuser": user.is_superuser,
            "memberships": memberships,
        }
    )

    return serializer.data
