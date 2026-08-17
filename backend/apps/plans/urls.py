from django.urls import path
from rest_framework.routers import DefaultRouter

from .calendar_views import calendar, warmup
from .dashboard import dashboard
from .views import RaceViewSet

router = DefaultRouter()
router.register("races", RaceViewSet, basename="race")

urlpatterns = router.urls + [
    path("dashboard/", dashboard, name="dashboard"),
    path("calendar/", calendar, name="calendar"),
    path("warmup/", warmup, name="warmup"),
]
