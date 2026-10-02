from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.obligaciones.enums import EstadoObligacion

from . import selectors
from .services import asistente_ia
from .services import insights as servicio_insights

# Los colores de estado son los mismos que en el resto de la aplicación (§22):
# un gráfico que use otra paleta obliga a releer la leyenda.
COLORES_ESTADO = {
    EstadoObligacion.PENDIENTE: "#4B5563",
    EstadoObligacion.PROXIMA_VENCER: "#B45309",
    EstadoObligacion.VENCIDA: "#DC2626",
    EstadoObligacion.PAGADA: "#16A34A",
}


@login_required
def estadisticas(request):
    """Módulo de analítica (§18).

    Los datos de los gráficos se serializan con `json_script` en la plantilla,
    que escapa el contenido: nunca se interpola JSON dentro de una etiqueta
    <script> a mano.
    """
    usuario = request.user
    hoy = timezone.localdate()

    datos_estado = selectors.por_estado(usuario, hoy)
    datos_categoria = selectors.por_categoria(usuario, hoy)
    evolucion = selectors.evolucion_mensual(usuario, meses=6, hoy=hoy)
    comprometido_mensual = selectors.comprometido_por_mes(usuario, meses_adelante=4, hoy=hoy)

    grafico_estado = {
        "etiquetas": [fila["etiqueta"] for fila in datos_estado],
        "cantidades": [fila["cantidad"] for fila in datos_estado],
        # Color de respaldo por si el CSS no estuviera disponible; el
        # navegador prefiere el token del tema activo (ver estadisticas.js).
        "colores": [COLORES_ESTADO[fila["estado"]] for fila in datos_estado],
        "claves": [fila["estado"] for fila in datos_estado],
    }

    # Paleta para las categorías que no tienen color propio (por si alguna
    # quedó sin asignar); las categorías normales ya traen el suyo.
    grafico_categoria = {
        "etiquetas": [fila["categoria__nombre"] for fila in datos_categoria],
        "valores": [float(fila["total"]) for fila in datos_categoria],
        "cantidades": [fila["cantidad"] for fila in datos_categoria],
        "colores": [fila["categoria__color"] for fila in datos_categoria],
    }

    grafico_evolucion = {
        "etiquetas": [fila["etiqueta"] for fila in evolucion],
        "pagado": [float(fila["pagado"]) for fila in evolucion],
        "sin_pagar": [float(fila["sin_pagar"]) for fila in evolucion],
    }

    grafico_comprometido = {
        "etiquetas": [fila["etiqueta"] for fila in comprometido_mensual],
        "valores": [float(fila["total"]) for fila in comprometido_mensual],
        "mes_actual": [fila["es_mes_actual"] for fila in comprometido_mensual],
    }

    contexto = {
        "totales": selectors.totales(usuario, hoy),
        "comprometido_este_mes": selectors.comprometido_este_mes(usuario, hoy),
        "quincena": selectors.gasto_por_quincena(usuario, hoy),
        "por_estado": datos_estado,
        "por_categoria": datos_categoria,
        "comprometido_mensual": comprometido_mensual,
        "proximos": selectors.proximos_vencimientos(usuario, limite=5, hoy=hoy),
        "cumplimiento": selectors.cumplimiento(usuario, hoy),
        "hay_datos": any(fila["cantidad"] for fila in datos_estado),
        "asistente_disponible": asistente_ia.disponible(),
        # `json_script` en la plantilla hace su propio json.dumps: pasarle
        # aquí un dict tal cual, nunca una cadena ya serializada, o el
        # resultado queda codificado dos veces y el navegador recibe texto
        # en vez de un objeto (el bug real detrás de los gráficos vacíos).
        "grafico_estado": grafico_estado,
        "grafico_categoria": grafico_categoria,
        "grafico_evolucion": grafico_evolucion,
        "grafico_comprometido": grafico_comprometido,
    }
    return render(request, "analitica/estadisticas.html", contexto)


@login_required
def insights(request):
    """PAYRECORD Insights (§19).

    Observaciones derivadas por reglas de los datos del usuario. No hay
    modelo de IA detrás y la plantilla lo dice explícitamente: presentarlo
    de otro modo sería simular algo que no existe.
    """
    hoy = timezone.localdate()

    return render(request, "analitica/insights.html", {
        "hoy": hoy,
        "insights": servicio_insights.generar(request.user, hoy),
        "total_reglas": len(servicio_insights.REGLAS),
        "asistente_disponible": asistente_ia.disponible(),
    })


@login_required
@require_POST
def asistente_preguntar(request):
    """Endpoint de PayRecord AI (solo lectura: nunca escribe nada).

    Recibe una pregunta en lenguaje natural y devuelve la respuesta de la
    IA, construida solo a partir de los datos reales del usuario que hace
    la petición — `asistente_ia` nunca mezcla datos de otro usuario porque
    cada herramienta es un cierre sobre `request.user`, nunca un parámetro
    que Gemini pueda elegir.

    El historial reciente vive en la sesión del navegador (no en la base de
    datos): es memoria de corto plazo para que "¿y en enero?" tenga sentido
    después de "¿cuánto debo en diciembre?", no un registro permanente.
    """
    pregunta = (request.POST.get("pregunta") or "").strip()
    resumen = request.POST.get("resumen") == "1"

    if not asistente_ia.disponible():
        return JsonResponse(
            {"error": "PayRecord AI todavía no está configurado en este equipo."},
            status=503,
        )
    if not resumen and not pregunta:
        return JsonResponse({"error": "Escribe una pregunta."}, status=400)
    if len(pregunta) > 500:
        return JsonResponse({"error": "La pregunta es demasiado larga."}, status=400)

    historial = request.session.get("asistente_ia_historial", [])

    try:
        if resumen:
            respuesta = asistente_ia.generar_resumen(request.user, historial=historial)
        else:
            respuesta = asistente_ia.preguntar(request.user, pregunta, historial=historial)
    except asistente_ia.AsistenteError as error:
        return JsonResponse({"error": str(error)}, status=502)

    pregunta_guardada = asistente_ia.PREGUNTA_RESUMEN if resumen else pregunta
    historial.append({"pregunta": pregunta_guardada, "respuesta": respuesta})
    request.session["asistente_ia_historial"] = historial[-asistente_ia.TURNOS_DE_HISTORIAL:]

    return JsonResponse({"respuesta": respuesta})
