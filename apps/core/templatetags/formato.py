"""Filtros de presentación para PAYRECORD.

Evitan meter lógica de formato dentro de los templates (§35).
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def moneda_cop(valor):
    """Formatea un valor como pesos colombianos: 1250000 -> $1.250.000

    Los montos se almacenan con dos decimales, pero en pantalla se muestran
    redondeados a peso, que es como se manejan los importes en Colombia.
    """
    if valor is None or valor == "":
        return "$0"
    try:
        numero = Decimal(valor).quantize(Decimal("1"))
    except (InvalidOperation, TypeError, ValueError):
        return "$0"

    signo = "-" if numero < 0 else ""
    entero = f"{abs(numero):,}".replace(",", ".")
    return f"{signo}${entero}"


@register.filter
def dias_restantes(fecha_vencimiento):
    """Devuelve los días entre hoy y la fecha dada. Negativo si ya pasó."""
    if not isinstance(fecha_vencimiento, date):
        return None
    return (fecha_vencimiento - timezone.localdate()).days


@register.filter
def texto_vencimiento(fecha_vencimiento):
    """Frase legible del vencimiento: 'Vence mañana', 'Vencida hace 3 días'."""
    dias = dias_restantes(fecha_vencimiento)
    if dias is None:
        return ""
    if dias < -1:
        return f"Vencida hace {abs(dias)} días"
    if dias == -1:
        return "Vencida ayer"
    if dias == 0:
        return "Vence hoy"
    if dias == 1:
        return "Vence mañana"
    return f"Vence en {dias} días"
