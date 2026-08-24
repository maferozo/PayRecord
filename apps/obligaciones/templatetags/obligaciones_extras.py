"""Presentación de estados y prioridades, fuera de los templates (§35)."""

from django import template

from apps.obligaciones.enums import EstadoObligacion, Prioridad

register = template.Library()

ICONOS_ESTADO = {
    EstadoObligacion.PENDIENTE: "bi-circle",
    EstadoObligacion.PROXIMA_VENCER: "bi-exclamation-circle",
    EstadoObligacion.VENCIDA: "bi-x-circle",
    EstadoObligacion.PAGADA: "bi-check-circle",
}


@register.filter
def etiqueta_estado(valor):
    """'VENCIDA' -> 'Vencida'"""
    try:
        return EstadoObligacion(valor).label
    except ValueError:
        return valor or ""


@register.filter
def clase_estado(valor):
    """'VENCIDA' -> 'pr-estado-vencida' (ver payrecord.css)"""
    if not valor:
        return "pr-estado-pendiente"
    return f"pr-estado-{str(valor).lower()}"


@register.filter
def icono_estado(valor):
    try:
        return ICONOS_ESTADO.get(EstadoObligacion(valor), "bi-circle")
    except ValueError:
        return "bi-circle"


@register.filter
def clase_prioridad(valor):
    """'ALTA' -> 'pr-prioridad-alta' (borde de color en la tarjeta)"""
    if not valor:
        return ""
    return f"pr-prioridad-{str(valor).lower()}"


@register.filter
def etiqueta_prioridad(valor):
    try:
        return Prioridad(valor).label
    except ValueError:
        return valor or ""
