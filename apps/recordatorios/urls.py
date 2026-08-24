from django.urls import path

from . import views

app_name = "recordatorios"

urlpatterns = [
    path("", views.BandejaView.as_view(), name="bandeja"),
    path("programados/", views.ProgramadosView.as_view(), name="programados"),
    path("<int:pk>/abrir/", views.abrir_notificacion, name="abrir"),
    path("leer-todas/", views.marcar_todas_leidas, name="leer_todas"),
]
