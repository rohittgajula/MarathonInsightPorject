from django.urls import path
from rest_framework.routers import DefaultRouter

from .calendar_views import (
    calendar, day_review, exercise_library, fueling, niggles, race_plan,
    technique, warmup, weekly,
)
from .dashboard import dashboard
from .views import RaceViewSet

router = DefaultRouter()
router.register("races", RaceViewSet, basename="race")

urlpatterns = router.urls + [
    path("dashboard/", dashboard, name="dashboard"),
    path("calendar/", calendar, name="calendar"),
    path("day-review/", day_review, name="day-review"),
    path("warmup/", warmup, name="warmup"),
    path("fueling/", fueling, name="fueling"),
    path("exercises/", exercise_library, name="exercises"),
    path("technique/", technique, name="technique"),
    path("weekly/", weekly, name="weekly"),
    path("niggles/", niggles, name="niggles"),
    path("race-plan/", race_plan, name="race-plan"),
]
