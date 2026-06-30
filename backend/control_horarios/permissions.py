from .models import CallCenterLocation, TenantMembership


def user_can_manage_location(user, location):
    if not location.is_active:
        return False

    if user.is_superuser:
        return True

    return TenantMembership.objects.filter(
        tenant=location.tenant,
        user=user,
        role=TenantMembership.Role.ADMIN,
        is_active=True,
    ).exists()


def user_can_view_location(user, location):
    if not location.is_active:
        return False

    if user.is_superuser:
        return True

    return TenantMembership.objects.filter(
        tenant=location.tenant,
        user=user,
        is_active=True,
    ).exists()


def get_manageable_locations(user):
    queryset = CallCenterLocation.objects.select_related("tenant").filter(is_active=True)

    if user.is_superuser:
        return queryset.all()

    return queryset.filter(
        tenant__memberships__user=user,
        tenant__memberships__is_active=True,
    ).distinct()
