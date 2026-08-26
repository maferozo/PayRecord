import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.obligaciones.enums import EstadoObligacion

from . import selectors
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

    grafico_estado = {
        "etiquetas": [fila["etiqueta"] for fila in datos_estado],
        "cantidades": [fila["cantidad"] for fila in datos_estado],
        # Color de respaldo por si el CSS no estuviera disponible; el
        # navegador prefiere el token del tema activo (ver estadisticas.js).
        "colores": [COLORES_ESTADO[fila["estado"]] for fila in datos_estado],
        "claves": [fila["estado"] for fila in datos_estado],
    }

    grafico_categoria = {
        "etiquetas": [fila["categoria__nombre"] for fila in datos_categoria],
        "valores": [float(fila["total"]) for fila in datos_categoria],
        "colores": [fila["categoria__color"] for fila in datos_categoria],
    }

    grafico_evolucion = {
        "etiquetas": [fila["etiqueta"] for fila in evolucion],
        "pagado": [float(fila["pagado"]) for fila in evolucion],
        "sin_pagar": [float(fila["sin_pagar"]) for fila in evolucion],
    }

    contexto = {
        "totales": selectors.totales(usuario, hoy),
        "por_estado": datos_estado,
        "por_categoria": datos_categoria,
        "cumplimiento": selectors.cumplimiento(usuario, hoy),
        "hay_datos": any(fila["cantidad"] for fila in datos_estado),
        "grafico_estado": json.dumps(grafico_estado),
        "grafico_categoria": json.dumps(grafico_categoria),
        "grafico_evolucion": json.dumps(grafico_evolucion),
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
    })
