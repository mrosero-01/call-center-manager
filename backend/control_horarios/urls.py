from django.urls import path

from .views import CallCenterLocationListView, OperationScheduleUpdateView


urlpatterns = [
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
]
