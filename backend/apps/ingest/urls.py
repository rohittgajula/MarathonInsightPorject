from django.urls import path
from rest_framework.routers import DefaultRouter

from .garmin_views import garmin_status, garmin_sync
from .views import RawFitFileViewSet

router = DefaultRouter()
router.register("uploads", RawFitFileViewSet, basename="rawfitfile")

urlpatterns = router.urls + [
    path("garmin/status/", garmin_status, name="garmin-status"),
    path("garmin/sync/", garmin_sync, name="garmin-sync"),
]
