from rest_framework.routers import DefaultRouter

from .views import DailyLogViewSet

router = DefaultRouter()
router.register("logs", DailyLogViewSet, basename="dailylog")

urlpatterns = router.urls
