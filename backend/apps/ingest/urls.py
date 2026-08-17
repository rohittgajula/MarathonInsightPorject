from django.urls import path
from rest_framework.routers import DefaultRouter

from .garmin_views import garmin_connect, garmin_disconnect, garmin_status, garmin_sync
from .views import RawFitFileViewSet

router = DefaultRouter()
router.register("uploads", RawFitFileViewSet, basename="rawfitfile")

urlpatterns = router.urls + [
    path("garmin/status/", garmin_status, name="garmin-status"),
    path("garmin/sync/", garmin_sync, name="garmin-sync"),
    path("garmin/connect/", garmin_connect, name="garmin-connect"),
    path("garmin/disconnect/", garmin_disconnect, name="garmin-disconnect"),
]
