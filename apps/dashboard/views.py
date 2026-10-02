from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from . import calendario as cal
from . import selectors


def _catch_up_recordatorios(request, hoy):
    """Genera los periodos y recordatorios atrasados al abrir el dashboard.

    La tarea programada no corre si el equipo estaba apagado, lo que en un
    portátil pasa casi siempre. Como ambos procesos son idempotentes por
    restricción de base de datos, dispararlos aquí no puede duplicar nada.
    Se limita a una vez al día por sesión para no repetir trabajo inútil.

    Los periodos se generan primero (§obligaciones mensuales): un mes nuevo
    tiene que existir antes de que pueda tener sus propios recordatorios.
    """
    marca = request.session.get("ultimo_catchup")
    if marca == hoy.isoformat():
        return

    from apps.obligaciones.services.recurrencia import generar as generar_periodos
    from apps.recordatorios.services.generacion import procesar

    generar_periodos(hoy=hoy, usuario=request.user)
    procesar(hoy=hoy, usuario=request.user)
    request.session["ultimo_catchup"] = hoy.isoformat()


@login_required
def inicio(request):
    """Dashboard: la pantalla principal de PAYRECORD (§11)."""
    usuario = request.user
    hoy = timezone.localdate()

    _catch_up_recordatorios(request, hoy)

    # Reutiliza el cálculo ya construido para /estadisticas/: el dashboard
    # no vuelve a calcular nada, solo muestra la misma serie en otra pantalla.
    from apps.analitica.selectors import comprometido_por_mes
    from apps.analitica.services import asistente_ia

    comprometido_mensual = comprometido_por_mes(usuario, meses_adelante=4, hoy=hoy)
    resumen = selectors.resumen(usuario, hoy)

    porcentaje_pagadas = (
        round(resumen["pagadas"]["cantidad"] * 100 / resumen["total_obligaciones"])
        if resumen["total_obligaciones"] else None
    )

    contexto = {
        "hoy": hoy,
        "resumen": resumen,
        "porcentaje_pagadas": porcentaje_pagadas,
        "proximas": selectors.proximas_obligaciones(usuario, limite=6, hoy=hoy),
        "por_categoria": selectors.gasto_por_categoria(usuario, hoy=hoy),
        "proveedores": selectors.principales_proveedores(usuario, hoy=hoy),
        "comprometido_mensual": comprometido_mensual,
        "grafico_comprometido": {
            "etiquetas": [fila["etiqueta"] for fila in comprometido_mensual],
            "valores": [float(fila["total"]) for fila in comprometido_mensual],
            # El mes en curso se resalta con otro tono en la gráfica: no es
            # solo estética, ayuda a distinguir "esto ya es real" de "esto
            # es lo que generaron las obligaciones mensuales por adelantado".
            "mes_actual": [fila["es_mes_actual"] for fila in comprometido_mensual],
        },
        "grafico_estado_dashboard": {
            "cantidades": [
                resumen["pagadas"]["cantidad"],
                resumen["pendientes"]["cantidad"] + resumen["proximas"]["cantidad"] + resumen["vencidas"]["cantidad"],
            ],
            "porcentaje": porcentaje_pagadas,
        },
        "asistente_disponible": asistente_ia.disponible(),
    }
    return render(request, "dashboard/inicio.html", contexto)


@login_required
def calendario(request):
    """Vista mensual de vencimientos (§24).

    Acepta ?anio= y ?mes= para navegar, y ?dia= para abrir el detalle de una
    fecha. Cualquier parámetro inválido cae al mes actual en lugar de fallar.
    """
    usuario = request.user
    hoy = timezone.localdate()

    _catch_up_recordatorios(request, hoy)

    anio, mes = cal.normalizar_mes(
        request.GET.get("anio", hoy.year), request.GET.get("mes", hoy.month), hoy
    )

    obligaciones = selectors.obligaciones_del_mes(usuario, anio, mes, hoy=hoy)
    semanas = cal.construir_mes(anio, mes, obligaciones, hoy)

    # Detalle del día seleccionado, si lo hay.
    dia_seleccionado = None
    obligaciones_dia = []
    try:
        numero_dia = int(request.GET.get("dia", ""))
        dia_seleccionado = date(anio, mes, numero_dia)
    except (TypeError, ValueError):
        dia_seleccionado = None

    if dia_seleccionado:
        obligaciones_dia = selectors.obligaciones_del_dia(usuario, dia_seleccionado, hoy=hoy)

    anio_anterior, mes_anterior = cal.mes_anterior(anio, mes)
    anio_siguiente, mes_siguiente = cal.mes_siguiente(anio, mes)

    contexto = {
        "hoy": hoy,
        "anio": anio,
        "mes": mes,
        "nombre_mes": cal.nombre_mes(anio, mes),
        "dias_semana": cal.DIAS_SEMANA,
        "semanas": semanas,
        "dia_seleccionado": dia_seleccionado,
        "obligaciones_dia": obligaciones_dia,
        "total_dia": sum((o.monto for o in obligaciones_dia), 0),
        "anterior": {"anio": anio_anterior, "mes": mes_anterior},
        "siguiente": {"anio": anio_siguiente, "mes": mes_siguiente},
        "total_mes": sum(
            (o.monto for o in obligaciones if o.fecha_vencimiento.month == mes), 0
        ),
        "cantidad_mes": sum(1 for o in obligaciones if o.fecha_vencimiento.month == mes),
    }
    return render(request, "dashboard/calendario.html", contexto)
