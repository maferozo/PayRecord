from django.urls import path

from . import views

app_name = "analitica"

urlpatterns = [
    path("", views.estadisticas, name="estadisticas"),
]
