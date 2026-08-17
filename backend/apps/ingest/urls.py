from rest_framework.routers import DefaultRouter

from .views import RawFitFileViewSet

router = DefaultRouter()
router.register("uploads", RawFitFileViewSet, basename="rawfitfile")

urlpatterns = router.urls
