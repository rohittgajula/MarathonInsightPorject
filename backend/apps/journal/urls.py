from rest_framework.routers import DefaultRouter

from .views import DailyLogViewSet, JournalEntryViewSet

router = DefaultRouter()
router.register("logs", DailyLogViewSet, basename="dailylog")
router.register("journal", JournalEntryViewSet, basename="journalentry")

urlpatterns = router.urls
