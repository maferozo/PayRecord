"""Agregados para el módulo de estadísticas (§18).

Como el dashboard, esta app solo lee. Todas las consultas parten de
`Obligacion.objects.para_usuario`, así que el aislamiento entre usuarios se
hereda del manager y no se reimplementa aquí.
"""

from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.obligaciones.enums import EstadoObligacion
from apps.obligaciones.models import Obligacion

MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic"]

CERO = Coalesce(Sum("monto"), Decimal("0"), output_field=DecimalField())


def _consulta(usuario, hoy):
    return Obligacion.objects.para_usuario(usuario, hoy=hoy)


def totales(usuario, hoy=None):
    """Las cifras de cabecera de §18."""
    hoy = hoy or timezone.localdate()
    consulta = _consulta(usuario, hoy)

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
    """Cantidad y valor en cada uno de los cuatro estados (§18)."""
    hoy = hoy or timezone.localdate()

    filas = {
        fila["estado"]: fila
        for fila in _consulta(usuario, hoy)
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
    """Cantidad y valor por categoría, de mayor a menor (§18)."""
    hoy = hoy or timezone.localdate()

    return list(
        _consulta(usuario, hoy)
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
