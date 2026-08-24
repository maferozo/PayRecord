"""Consultas de solo lectura del dashboard (§11).

Esta app no tiene modelos: solo lee lo que exponen `obligaciones` y
`usuarios`. Al no escribir nada, no puede introducir inconsistencias.
"""

from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.obligaciones.enums import EstadoObligacion
from apps.obligaciones.models import Obligacion
from apps.obligaciones.services.priorizacion import construir_contexto, priorizar


def _consulta_base(usuario, hoy):
    return Obligacion.objects.para_usuario(usuario, hoy=hoy).select_related("categoria")


def resumen(usuario, hoy=None):
    """Conteos y sumas por estado, en una sola consulta agregada (§11)."""
    hoy = hoy or timezone.localdate()

    filas = (
        _consulta_base(usuario, hoy)
        .values("estado")
        .annotate(cantidad=Count("id"), total=Sum("monto"))
    )

    vacio = {"cantidad": 0, "total": Decimal("0")}
    por_estado = {estado.value: dict(vacio) for estado in EstadoObligacion}

    for fila in filas:
        por_estado[fila["estado"]] = {
            "cantidad": fila["cantidad"],
            "total": fila["total"] or Decimal("0"),
        }

    pendientes = por_estado[EstadoObligacion.PENDIENTE]
    proximas = por_estado[EstadoObligacion.PROXIMA_VENCER]
    vencidas = por_estado[EstadoObligacion.VENCIDA]
    pagadas = por_estado[EstadoObligacion.PAGADA]

    # "Dinero comprometido" es todo lo que aún no se ha pagado, sin importar
    # en cuál de los tres estados sin pagar esté (§11).
    comprometido = pendientes["total"] + proximas["total"] + vencidas["total"]

    return {
        "pendientes": pendientes,
        "proximas": proximas,
        "vencidas": vencidas,
        "pagadas": pagadas,
        "comprometido": comprometido,
        "total_obligaciones": sum(d["cantidad"] for d in por_estado.values()),
    }


def proximas_obligaciones(usuario, limite=6, hoy=None):
    """Las que vencen antes, sin pagar, ordenadas por fecha (§11)."""
    hoy = hoy or timezone.localdate()
    return list(_consulta_base(usuario, hoy).proximas()[:limite])


def prioridades_del_dia(usuario, limite=5, hoy=None):
    """Qué debería atender primero, con el motivo de cada una (§12).

    El orden lo decide el algoritmo de priorización, no la fecha.
    """
    hoy = hoy or timezone.localdate()

    pendientes = list(_consulta_base(usuario, hoy).pendientes_de_pago())
    if not pendientes:
        return []

    contexto = construir_contexto(pendientes, hoy)
    return priorizar(pendientes, contexto)[:limite]


def gasto_por_categoria(usuario, hoy=None, limite=6):
    """Reparto del dinero comprometido por categoría.

    Alimenta el bloque de proveedores y categorías del dashboard empresarial
    y sirve de base para las estadísticas de la Fase 8.
    """
    hoy = hoy or timezone.localdate()

    return list(
        _consulta_base(usuario, hoy)
        .pendientes_de_pago()
        .values("categoria__nombre", "categoria__color", "categoria__icono")
        .annotate(total=Sum("monto"), cantidad=Count("id"))
        .order_by("-total")[:limite]
    )


def obligaciones_del_mes(usuario, anio, mes, hoy=None):
    """Obligaciones que vencen dentro de la cuadrícula de un mes (§24).

    Incluye los días visibles de los meses vecinos, para que las celdas de
    relleno del calendario también muestren su contenido.
    """
    import calendar as _calendar

    hoy = hoy or timezone.localdate()

    semanas = _calendar.Calendar(_calendar.MONDAY).monthdatescalendar(anio, mes)
    desde, hasta = semanas[0][0], semanas[-1][-1]

    return list(
        _consulta_base(usuario, hoy)
        .filter(fecha_vencimiento__range=(desde, hasta))
        .order_by("fecha_vencimiento", "-monto")
    )


def obligaciones_del_dia(usuario, fecha, hoy=None):
    """Detalle de una fecha concreta del calendario (§24)."""
    hoy = hoy or timezone.localdate()
    return list(
        _consulta_base(usuario, hoy)
        .filter(fecha_vencimiento=fecha)
        .order_by("-monto")
    )


def principales_proveedores(usuario, limite=5, hoy=None):
    """Top de proveedores por monto pendiente (§26).

    Solo tiene sentido en cuentas de empresa. Agrupa por el texto del campo
    `proveedor`; si más adelante hace falta agrupar de forma fiable, se
    evaluará una tabla Proveedor (decisión D4).
    """
    if not usuario.es_empresa:
        return []

    hoy = hoy or timezone.localdate()

    return list(
        _consulta_base(usuario, hoy)
        .pendientes_de_pago()
        .exclude(proveedor="")
        .values("proveedor")
        .annotate(total=Sum("monto"), cantidad=Count("id"))
        .order_by("-total")[:limite]
    )
