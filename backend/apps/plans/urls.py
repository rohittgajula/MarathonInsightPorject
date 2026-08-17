from django.urls import path
from rest_framework.routers import DefaultRouter

from .calendar_views import calendar, niggles, race_plan, technique, warmup, weekly
from .dashboard import dashboard
from .views import RaceViewSet

router = DefaultRouter()
router.register("races", RaceViewSet, basename="race")

urlpatterns = router.urls + [
    path("dashboard/", dashboard, name="dashboard"),
    path("calendar/", calendar, name="calendar"),
    path("warmup/", warmup, name="warmup"),
    path("technique/", technique, name="technique"),
    path("weekly/", weekly, name="weekly"),
    path("niggles/", niggles, name="niggles"),
    path("race-plan/", race_plan, name="race-plan"),
]
