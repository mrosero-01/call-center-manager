from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator

from .application.commands import ScheduleDayInput, UpdateOperationScheduleCommand
from .application.use_cases import UpdateOperationSchedule
from .infrastructure.asterisk.ami_client import AmiClientError
from .infrastructure.asterisk.factories import build_schedule_publisher
from .infrastructure.django.repositories import DjangoScheduleRepository
from .models import CallCenterLocation, ScheduleChangeLog, TenantMembership
from .permissions import (
    get_manageable_locations,
    user_can_manage_location,
    user_can_view_location,
)
from .serializers import (
    CallCenterLocationSerializer,
    CurrentUserSerializer,
    LoginSerializer,
    ScheduleChangeLogSerializer,
    UpdateOperationScheduleSerializer,
)


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

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

        command = self._build_command(
            user_id=request.user.id,
            tenant_id=location.tenant_id,
            location_id=location.id,
            validated_data=serializer.validated_data,
        )
        use_case = UpdateOperationSchedule(
            repository=DjangoScheduleRepository(),
            publisher=build_schedule_publisher(),
        )

        try:
            result = use_case.execute(command)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (AmiClientError, OSError) as exc:
            return Response(
                {
                    "detail": "El horario se guardo, pero no se pudo sincronizar con Asterisk.",
                    "asterisk_error": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(result, status=status.HTTP_200_OK)

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
