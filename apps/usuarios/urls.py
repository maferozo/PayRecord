from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from . import views

app_name = "usuarios"

urlpatterns = [
    path("registro/", views.RegistroView.as_view(), name="registro"),
    path("entrar/", views.InicioSesionView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("perfil/", views.perfil, name="perfil"),

    # --- Recuperación de contraseña (§6) ---
    path(
        "recuperar/",
        auth_views.PasswordResetView.as_view(
            template_name="usuarios/password_reset.html",
            email_template_name="usuarios/password_reset_email.html",
            subject_template_name="usuarios/password_reset_asunto.txt",
            success_url=reverse_lazy("usuarios:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="usuarios/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "recuperar/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="usuarios/password_reset_confirm.html",
            success_url=reverse_lazy("usuarios:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "recuperar/listo/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="usuarios/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # --- Cambio de contraseña desde el perfil ---
    path(
        "contrasena/",
        auth_views.PasswordChangeView.as_view(
            template_name="usuarios/password_change.html",
            success_url=reverse_lazy("usuarios:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "contrasena/listo/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="usuarios/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
