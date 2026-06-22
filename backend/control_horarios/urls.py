from django.urls import path

from .views import OperationScheduleUpdateView


urlpatterns = [
    path(
        "locations/<int:location_id>/schedule/",
        OperationScheduleUpdateView.as_view(),
        name="operation-schedule-update",
    ),
]
