import hmac
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .models import Notificacion, Recordatorio

_LOGGER = logging.getLogger(__name__)


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


@csrf_exempt
@require_POST
def ejecutar_tarea_diaria(request):
    """Reemplazo sin costo de un WebJob (§15, §16).

    El plan de Azure App Service de este despliegue es el gratuito (F1), que
    no admite WebJobs ni ninguna tarea programada propia de Azure (ver
    docs/despliegue-azure.md, §10). Este endpoint es a lo que llama, una vez
    al día, el workflow programado de GitHub Actions
    (.github/workflows/tarea-diaria.yml) — gratis y ya disponible porque el
    código ya vive en GitHub.

    No usa `@login_required`: quien llama es un proceso externo, no una
    persona con sesión. En su lugar exige el token compartido, para que no
    cualquiera en internet pueda dispararlo a voluntad (el plan gratuito
    tiene una cuota de CPU limitada por día).

    Procesa a todos los usuarios -- no hay "usuario actual" en una llamada
    así --, y es seguro ejecutarlo más de una vez el mismo día: tanto la
    generación de periodos como la de recordatorios son idempotentes.
    """
    token_esperado = settings.TAREA_DIARIA_TOKEN
    if not token_esperado:
        return JsonResponse(
            {"error": "TAREA_DIARIA_TOKEN no está configurado en este entorno."},
            status=503,
        )

    token_recibido = request.headers.get("X-Tarea-Token", "")
    if not hmac.compare_digest(token_recibido, token_esperado):
        _LOGGER.warning("Intento de ejecutar la tarea diaria con un token inválido.")
        return JsonResponse({"error": "Token inválido."}, status=403)

    from apps.obligaciones.services.recurrencia import generar as generar_periodos
    from apps.recordatorios.services.generacion import procesar

    periodos_creados = generar_periodos()
    resultado = procesar()

    _LOGGER.info(
        "Tarea diaria ejecutada: %s periodo(s), %s recordatorio(s) creados, "
        "%s enviados, %s con error.",
        periodos_creados, resultado["creados"], resultado["enviados"], resultado["errores"],
    )

    return JsonResponse({"periodos_creados": periodos_creados, **resultado})


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
