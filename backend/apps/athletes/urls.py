from rest_framework.authtoken.views import obtain_auth_token
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AthleteViewSet

router = DefaultRouter()
router.register("athletes", AthleteViewSet, basename="athlete")

urlpatterns = router.urls + [
    path("auth/token/", obtain_auth_token, name="obtain-token"),
]
