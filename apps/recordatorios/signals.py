"""Sincronización automática de recordatorios.

Se hace por señal y no llamando al servicio desde `Obligacion` para no
invertir la dirección de las dependencias: `recordatorios` conoce a
`obligaciones`, nunca al revés.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.obligaciones.models import Obligacion

from .services.generacion import sincronizar


@receiver(post_save, sender=Obligacion)
def sincronizar_recordatorios(sender, instance, created, **kwargs):
    """Cancela los avisos pendientes que hayan quedado sin sentido.

    Ocurre al marcar la obligación como pagada, al eliminarla o al mover su
    fecha de vencimiento.
    """
    if created:
        return  # una obligación recién creada todavía no tiene reglas
    sincronizar(instance)
