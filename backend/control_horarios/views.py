from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .application.commands import ScheduleDayInput, UpdateOperationScheduleCommand
from .application.use_cases import UpdateOperationSchedule
from .infrastructure.asterisk.factories import build_schedule_publisher
from .infrastructure.django.repositories import DjangoScheduleRepository
from .models import CallCenterLocation, TenantMembership
from .serializers import UpdateOperationScheduleSerializer


class OperationScheduleUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, location_id):
        location = get_object_or_404(CallCenterLocation, id=location_id)

        if not self._user_can_change_location(request.user, location):
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

        return Response(result, status=status.HTTP_200_OK)

    def _user_can_change_location(self, user, location):
        if user.is_superuser:
            return True

        return TenantMembership.objects.filter(
            tenant=location.tenant,
            user=user,
            role=TenantMembership.Role.ADMIN,
            is_active=True,
        ).exists()

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
