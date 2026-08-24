"""Rutas raíz de PAYRECORD."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("cuenta/", include("apps.usuarios.urls")),
    # Fase 4: path("obligaciones/", include("apps.obligaciones.urls")),
    # Fase 5: path("dashboard/", include("apps.dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
