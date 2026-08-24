from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import ListView

from .models import Notificacion, Recordatorio


class BandejaView(LoginRequiredMixin, ListView):
    """Notificaciones recibidas (§14, canal 1)."""

    model = Notificacion
    template_name = "recordatorios/bandeja.html"
    context_object_name = "notificaciones"
    paginate_by = 20

    def get_queryset(self):
        consulta = Notificacion.objects.de(self.request.user).select_related(
            "recordatorio", "recordatorio__obligacion"
        )
        if self.request.GET.get("filtro") == "no-leidas":
            consulta = consulta.no_leidas()
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["no_leidas"] = Notificacion.objects.de(self.request.user).no_leidas().count()
        contexto["filtro"] = self.request.GET.get("filtro", "")
        return contexto


@login_required
def abrir_notificacion(request, pk):
    """Marca como leída y lleva a la obligación.

    El momento de lectura queda registrado: es el dato que necesitará §20
    para saber qué recordatorios le sirven realmente al usuario.
    """
    notificacion = get_object_or_404(Notificacion.objects.de(request.user), pk=pk)
    notificacion.marcar_leida()

    if notificacion.url_destino:
        return redirect(notificacion.url_destino)
    return redirect("recordatorios:bandeja")


@login_required
def marcar_todas_leidas(request):
    if request.method != "POST":
        return redirect("recordatorios:bandeja")

    actualizadas = Notificacion.objects.de(request.user).no_leidas().update(
        leida=True, fecha_lectura=timezone.now()
    )
    if actualizadas:
        messages.success(request, f"{actualizadas} notificación(es) marcadas como leídas.")
    return redirect("recordatorios:bandeja")


class ProgramadosView(LoginRequiredMixin, ListView):
    """Recordatorios programados del usuario, para que sepa qué va a recibir."""

    model = Recordatorio
    template_name = "recordatorios/programados.html"
    context_object_name = "recordatorios"
    paginate_by = 30

    def get_queryset(self):
        return (
            Recordatorio.objects.de_usuario(self.request.user)
            .select_related("obligacion", "obligacion__categoria")
            .order_by("estado", "fecha_programada")
        )
