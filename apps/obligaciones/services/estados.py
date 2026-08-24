"""Cálculo del estado de una obligación (§9).

El estado NO se guarda en la base de datos: se deriva de `pagada`,
`fecha_pago` y `fecha_vencimiento` (decisión D3 del análisis). Así nunca
queda desfasado, ni siquiera al cambiar de día.

Este módulo expone dos caminos equivalentes:

- `calcular_estado`   → para una obligación suelta, en Python.
- `anotacion_estado`  → la misma regla en SQL, para poder filtrar y ordenar
                        listados sin traerlos a memoria.

Ambos deben dar siempre el mismo resultado; hay pruebas que lo verifican.
"""

from datetime import date, timedelta

from django.db.models import Case, CharField, Value, When

from apps.obligaciones.enums import EstadoObligacion

UMBRAL_POR_DEFECTO = 7


def calcular_estado(pagada, fecha_vencimiento, hoy=None, umbral_dias=UMBRAL_POR_DEFECTO):
    """Devuelve el estado de una obligación.

    Reglas, en este orden:
        pagada                          -> PAGADA
        vencimiento anterior a hoy      -> VENCIDA
        vencimiento dentro del umbral   -> PROXIMA_VENCER
        resto                           -> PENDIENTE
    """
    if pagada:
        return EstadoObligacion.PAGADA

    hoy = hoy or date.today()

    if fecha_vencimiento < hoy:
        return EstadoObligacion.VENCIDA

    if fecha_vencimiento <= hoy + timedelta(days=umbral_dias):
        return EstadoObligacion.PROXIMA_VENCER

    return EstadoObligacion.PENDIENTE


def anotacion_estado(hoy, umbral_dias=UMBRAL_POR_DEFECTO):
    """La misma regla, expresada como expresión SQL para `annotate`."""
    limite = hoy + timedelta(days=umbral_dias)

    return Case(
        When(pagada=True, then=Value(EstadoObligacion.PAGADA)),
        When(fecha_vencimiento__lt=hoy, then=Value(EstadoObligacion.VENCIDA)),
        When(fecha_vencimiento__lte=limite, then=Value(EstadoObligacion.PROXIMA_VENCER)),
        default=Value(EstadoObligacion.PENDIENTE),
        output_field=CharField(),
    )


def dias_para_vencer(fecha_vencimiento, hoy=None):
    """Días que faltan. Negativo si la fecha ya pasó."""
    hoy = hoy or date.today()
    return (fecha_vencimiento - hoy).days
