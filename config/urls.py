"""Rutas raíz de PAYRECORD."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("cuenta/", include("apps.usuarios.urls")),
    path("", include("apps.obligaciones.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("notificaciones/", include("apps.recordatorios.urls")),
    path("estadisticas/", include("apps.analitica.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
