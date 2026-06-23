from django.urls import path

from .views import (
    CallCenterLocationListView,
    CurrentUserView,
    LoginView,
    LogoutView,
    OperationScheduleUpdateView,
    ScheduleChangeLogListView,
)


urlpatterns = [
    path(
        "auth/login/",
        LoginView.as_view(),
        name="auth-login",
    ),
    path(
        "auth/logout/",
        LogoutView.as_view(),
        name="auth-logout",
    ),
    path(
        "me/",
        CurrentUserView.as_view(),
        name="current-user",
    ),
    path(
        "locations/",
        CallCenterLocationListView.as_view(),
        name="callcenter-location-list",
    ),
    path(
        "locations/<int:location_id>/schedule/",
        OperationScheduleUpdateView.as_view(),
        name="operation-schedule-update",
    ),
    path(
        "locations/<int:location_id>/schedule-changes/",
        ScheduleChangeLogListView.as_view(),
        name="schedule-change-log-list",
    ),
]
