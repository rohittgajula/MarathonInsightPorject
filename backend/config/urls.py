from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.athletes.urls")),
    path("api/", include("apps.ingest.urls")),
    path("api/", include("apps.activities.urls")),
    path("api/", include("apps.plans.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
