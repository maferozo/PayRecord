from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import ConfiguracionForm, EmpresaForm, LoginForm, PerfilForm, RegistroForm


class RegistroView(CreateView):
    """Alta de cuenta. Deja al usuario autenticado para evitar un login extra."""

    form_class = RegistroForm
    template_name = "usuarios/registro.html"
    success_url = reverse_lazy("core:inicio")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:inicio")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        login(self.request, self.object)
        messages.success(
            self.request,
            f"Bienvenido a PAYRECORD, {self.object.get_short_name()}.",
        )
        return respuesta


class InicioSesionView(LoginView):
    form_class = LoginForm
    template_name = "usuarios/login.html"
    redirect_authenticated_user = True


@login_required
def perfil(request):
    """Datos de la cuenta, empresa y preferencias, en una sola pantalla."""

    usuario = request.user
    configuracion = usuario.configuracion

    form_perfil = PerfilForm(instance=usuario, prefix="perfil")
    form_configuracion = ConfiguracionForm(instance=configuracion, prefix="config")
    form_empresa = (
        EmpresaForm(instance=usuario.empresa, prefix="empresa") if usuario.empresa else None
    )

    if request.method == "POST":
        seccion = request.POST.get("seccion")

        if seccion == "perfil":
            form_perfil = PerfilForm(request.POST, instance=usuario, prefix="perfil")
            if form_perfil.is_valid():
                form_perfil.save()
                messages.success(request, "Datos de la cuenta actualizados.")
                return redirect("usuarios:perfil")

        elif seccion == "config":
            form_configuracion = ConfiguracionForm(
                request.POST, instance=configuracion, prefix="config"
            )
            if form_configuracion.is_valid():
                form_configuracion.save()
                messages.success(request, "Preferencias actualizadas.")
                return redirect("usuarios:perfil")

        elif seccion == "empresa" and usuario.empresa:
            form_empresa = EmpresaForm(request.POST, instance=usuario.empresa, prefix="empresa")
            if form_empresa.is_valid():
                form_empresa.save()
                messages.success(request, "Datos de la empresa actualizados.")
                return redirect("usuarios:perfil")

        messages.error(request, "Revisa los datos marcados en rojo.")

    return render(
        request,
        "usuarios/perfil.html",
        {
            "form_perfil": form_perfil,
            "form_configuracion": form_configuracion,
            "form_empresa": form_empresa,
        },
    )
