"""Agregados para el módulo de estadísticas (§18).

Como el dashboard, esta app solo lee. Todas las consultas parten de
`Obligacion.objects.para_usuario`, así que el aislamiento entre usuarios se
hereda del manager y no se reimplementa aquí.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.obligaciones.enums import EstadoObligacion
from apps.obligaciones.models import Obligacion
from apps.obligaciones.services.estados import fin_de_mes

MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic"]

CERO = Coalesce(Sum("monto"), Decimal("0"), output_field=DecimalField())


def _consulta(usuario, hoy):
    return Obligacion.objects.para_usuario(usuario, hoy=hoy)


def _hasta_este_mes(usuario, hoy):
    """Descarta los meses que el generador de recurrencia ya creó por
    adelantado, pero que todavía no llegan (mismo criterio que
    `apps.dashboard.selectors._sin_periodos_futuros`).

    Una obligación que el usuario registró él mismo, por lejana que sea su
    fecha, sigue contando. La evolución mensual (`evolucion_mensual`) sí
    necesita ver todos los meses generados, por eso este límite no se aplica
    ahí.
    """
    return _consulta(usuario, hoy).exclude(
        Q(obligacion_recurrente__isnull=False) & Q(fecha_vencimiento__gt=fin_de_mes(hoy))
    )


def totales(usuario, hoy=None):
    """Las cifras de cabecera de §18, del mes en curso."""
    hoy = hoy or timezone.localdate()
    consulta = _hasta_este_mes(usuario, hoy)

    agregados = consulta.aggregate(
        cantidad=Count("id"),
        valor_total=CERO,
        pagado=Coalesce(
            Sum("monto", filter=Q(pagada=True)), Decimal("0"), output_field=DecimalField()
        ),
        vencido=Coalesce(
            Sum("monto", filter=Q(pagada=False, fecha_vencimiento__lt=hoy)),
            Decimal("0"), output_field=DecimalField(),
        ),
        pendiente=Coalesce(
            Sum("monto", filter=Q(pagada=False)), Decimal("0"), output_field=DecimalField()
        ),
    )

    pagadas = consulta.filter(pagada=True).count()
    agregados["cantidad_pagadas"] = pagadas
    agregados["porcentaje_pagado"] = (
        round(pagadas * 100 / agregados["cantidad"]) if agregados["cantidad"] else 0
    )
    return agregados


def por_estado(usuario, hoy=None):
    """Cantidad y valor en cada uno de los cuatro estados (§18), del mes en curso."""
    hoy = hoy or timezone.localdate()

    filas = {
        fila["estado"]: fila
        for fila in _hasta_este_mes(usuario, hoy)
        .values("estado")
        .annotate(cantidad=Count("id"), total=CERO)
    }

    resultado = []
    for estado in EstadoObligacion:
        fila = filas.get(estado.value, {})
        resultado.append({
            "estado": estado.value,
            "etiqueta": estado.label,
            "cantidad": fila.get("cantidad", 0),
            "total": fila.get("total", Decimal("0")),
        })
    return resultado


def por_categoria(usuario, hoy=None):
    """Cantidad y valor por categoría, de mayor a menor (§18), del mes en curso."""
    hoy = hoy or timezone.localdate()

    return list(
        _hasta_este_mes(usuario, hoy)
        .values("categoria__nombre", "categoria__color")
        .annotate(cantidad=Count("id"), total=CERO)
        .order_by("-total")
    )


def evolucion_mensual(usuario, meses=6, hoy=None):
    """Pagado frente a no pagado, mes a mes (§18: evolución de pagos).

    Se agrupa por mes de vencimiento y se rellenan los meses sin datos, para
    que el gráfico no tenga huecos que induzcan a error.
    """
    hoy = hoy or timezone.localdate()

    # Primer día del mes, `meses - 1` meses hacia atrás.
    total_meses = hoy.year * 12 + (hoy.month - 1) - (meses - 1)
    inicio = timezone.datetime(total_meses // 12, total_meses % 12 + 1, 1).date()

    filas = (
        _consulta(usuario, hoy)
        .filter(fecha_vencimiento__gte=inicio)
        .annotate(mes=TruncMonth("fecha_vencimiento"))
        .values("mes")
        .annotate(
            pagado=Coalesce(
                Sum("monto", filter=Q(pagada=True)), Decimal("0"), output_field=DecimalField()
            ),
            sin_pagar=Coalesce(
                Sum("monto", filter=Q(pagada=False)), Decimal("0"), output_field=DecimalField()
            ),
        )
        .order_by("mes")
    )

    datos = {fila["mes"]: fila for fila in filas}

    serie = []
    for desplazamiento in range(meses):
        indice = total_meses + desplazamiento
        anio, mes = indice // 12, indice % 12 + 1
        clave = timezone.datetime(anio, mes, 1).date()
        fila = datos.get(clave, {})

        serie.append({
            "etiqueta": f"{MESES_CORTOS[mes - 1]} {str(anio)[2:]}",
            "pagado": fila.get("pagado", Decimal("0")),
            "sin_pagar": fila.get("sin_pagar", Decimal("0")),
        })
    return serie


def comprometido_por_mes(usuario, meses_adelante=4, hoy=None):
    """Cuánto dinero vence cada uno de los próximos meses, se haya pagado o no.

    Distinto de `evolucion_mensual` (que mira hacia atrás, para juzgar el
    cumplimiento): esto mira hacia adelante y responde la pregunta que
    justamente motivó las obligaciones mensuales: "¿cuánto me toca en
    octubre?", no "¿qué tan bien pagué?". Por eso sí incluye los periodos
    que el generador de recurrencia ya creó por adelantado: aquí es
    justamente donde tiene sentido verlos.
    """
    hoy = hoy or timezone.localdate()
    inicio = hoy.replace(day=1)
    indice_inicio = inicio.year * 12 + (inicio.month - 1)

    filas = (
        _consulta(usuario, hoy)
        .filter(fecha_vencimiento__gte=inicio)
        .annotate(mes=TruncMonth("fecha_vencimiento"))
        .values("mes")
        .annotate(total=CERO)
    )
    datos = {fila["mes"]: fila["total"] for fila in filas}

    serie = []
    for desplazamiento in range(meses_adelante):
        indice = indice_inicio + desplazamiento
        anio, mes = indice // 12, indice % 12 + 1
        clave = timezone.datetime(anio, mes, 1).date()

        serie.append({
            "etiqueta": f"{MESES_CORTOS[mes - 1]} {str(anio)[2:]}",
            "total": datos.get(clave, Decimal("0")),
            "es_mes_actual": desplazamiento == 0,
        })
    return serie


def _total_del_mes(usuario, primer_dia, hoy):
    """Cuánto vence entre el primer y el último día de ese mes, en total."""
    ultimo_dia = fin_de_mes(primer_dia)
    return (
        _consulta(usuario, hoy)
        .filter(fecha_vencimiento__gte=primer_dia, fecha_vencimiento__lte=ultimo_dia)
        .aggregate(total=CERO)["total"]
    )


def comprometido_este_mes(usuario, hoy=None):
    """Estadística 1: la tarjeta principal.

    Compara el total de este mes con el del mes anterior, con los mismos
    datos reales — nunca se inventa el porcentaje: si no hubo nada
    registrado el mes pasado, no hay con qué comparar y se devuelve `None`.
    """
    hoy = hoy or timezone.localdate()
    inicio_actual = hoy.replace(day=1)

    indice_anterior = inicio_actual.year * 12 + (inicio_actual.month - 1) - 1
    anio_anterior, mes_anterior = divmod(indice_anterior, 12)
    inicio_anterior = date(anio_anterior, mes_anterior + 1, 1)

    actual = _total_del_mes(usuario, inicio_actual, hoy)
    anterior = _total_del_mes(usuario, inicio_anterior, hoy)

    porcentaje = None
    if anterior:
        porcentaje = round(float((actual - anterior) / anterior) * 100, 1)

    return {
        "actual": actual,
        "anterior": anterior,
        "porcentaje": porcentaje,
        "aumento": porcentaje is not None and porcentaje > 0,
    }


def gasto_por_quincena(usuario, hoy=None):
    """Estadística 3: cuánto concentra cada mitad del mes en curso.

    Primera quincena: días 1 a 15. Segunda: del 16 al último día del mes,
    sea 28, 29, 30 o 31. Igual que `comprometido_este_mes`, cuenta lo que
    vence sin importar si ya se pagó.
    """
    hoy = hoy or timezone.localdate()
    inicio = hoy.replace(day=1)
    fin = fin_de_mes(hoy)
    corte = inicio.replace(day=15)

    consulta = _consulta(usuario, hoy).filter(
        fecha_vencimiento__gte=inicio, fecha_vencimiento__lte=fin
    )

    primera = consulta.filter(fecha_vencimiento__lte=corte).aggregate(
        total=CERO, cantidad=Count("id")
    )
    segunda = consulta.filter(fecha_vencimiento__gt=corte).aggregate(
        total=CERO, cantidad=Count("id")
    )

    total = primera["total"] + segunda["total"]
    if total:
        porcentaje_primera = round(float(primera["total"] * 100 / total))
        porcentaje_segunda = 100 - porcentaje_primera
    else:
        porcentaje_primera = porcentaje_segunda = None

    primera["porcentaje"] = porcentaje_primera
    segunda["porcentaje"] = porcentaje_segunda

    return {"primera": primera, "segunda": segunda, "hay_datos": total > 0}


def mayores_gastos(usuario, limite=5, hoy=None):
    """Estadística 4: las obligaciones de este mes ordenadas de mayor a menor.

    Igual que las demás tarjetas del mes, mira lo que vence entre el primer
    y el último día del mes en curso. Devuelve también cuántas hay en total,
    para poder ofrecer "ver todas" cuando hay más de las que se muestran.
    """
    hoy = hoy or timezone.localdate()
    inicio = hoy.replace(day=1)
    fin = fin_de_mes(hoy)

    consulta = (
        _consulta(usuario, hoy)
        .filter(fecha_vencimiento__gte=inicio, fecha_vencimiento__lte=fin)
        .select_related("categoria")
    )

    return {
        "obligaciones": list(consulta.order_by("-monto")[:limite]),
        "total": consulta.count(),
        "desde": inicio,
        "hasta": fin,
    }


def proximos_vencimientos(usuario, limite=5, hoy=None):
    """Lo que vence más pronto, sin pagar (§18: próximos vencimientos)."""
    hoy = hoy or timezone.localdate()
    return list(
        _consulta(usuario, hoy)
        .filter(pagada=False)
        .select_related("categoria")
        .order_by("fecha_vencimiento")[:limite]
    )


def cumplimiento(usuario, hoy=None):
    """Qué proporción de lo ya pagado se pagó a tiempo.

    Es la métrica que responde a «¿cómo se comportan mis obligaciones?» (§38).
    Solo mira obligaciones pagadas con fecha de pago registrada.
    """
    hoy = hoy or timezone.localdate()

    pagadas = _consulta(usuario, hoy).filter(pagada=True, fecha_pago__isnull=False)
    total = pagadas.count()

    if not total:
        return {"total": 0, "a_tiempo": 0, "tarde": 0, "porcentaje": None}

    a_tiempo = pagadas.filter(fecha_pago__lte=F("fecha_vencimiento")).count()
    return {
        "total": total,
        "a_tiempo": a_tiempo,
        "tarde": total - a_tiempo,
        "porcentaje": round(a_tiempo * 100 / total),
    }
