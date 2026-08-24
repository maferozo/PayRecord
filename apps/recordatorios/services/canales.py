"""Canales de notificación (§14).

Añadir un canal nuevo consiste en escribir una clase y registrarla. Ni el
modelo `Recordatorio` ni el generador cambian: por eso la promesa de §14
("agregar canales sin rehacer el sistema") es real y no un deseo.

Estado actual:
    APP    → implementado (notificación dentro de la aplicación)
    EMAIL  → declarado, pendiente de la fase 7b
    WhatsApp → fuera de alcance (§31)
"""

from abc import ABC, abstractmethod

from django.urls import reverse

from apps.recordatorios.enums import CanalNotificacion
from apps.recordatorios.models import Notificacion


class CanalNoDisponible(Exception):
    """El canal existe en el modelo pero todavía no está implementado."""


class Canal(ABC):
    """Contrato que debe cumplir cualquier canal de entrega."""

    codigo = None

    @abstractmethod
    def enviar(self, recordatorio):
        """Entrega el recordatorio. Debe ser idempotente por recordatorio."""


class CanalInApp(Canal):
    """Notificación dentro de la aplicación. Es el canal del MVP."""

    codigo = CanalNotificacion.APP

    def enviar(self, recordatorio):
        obligacion = recordatorio.obligacion

        # Si ya se entregó por este canal, no se duplica.
        existente = recordatorio.notificaciones.first()
        if existente:
            return existente

        return Notificacion.objects.create(
            usuario=obligacion.usuario,
            recordatorio=recordatorio,
            titulo=self._titulo(recordatorio),
            mensaje=self._mensaje(recordatorio),
            url_destino=reverse("obligaciones:detalle", args=[obligacion.pk]),
        )

    def _titulo(self, recordatorio):
        """El texto describe la situación real en el momento de la entrega.

        No se usa `dias_antes` de la regla: cuando un aviso se recupera con
        retraso —porque el equipo estuvo apagado varios días— decir "vence
        mañana" de algo ya vencido sería engañoso.
        """
        from django.utils import timezone

        concepto = recordatorio.obligacion.concepto
        dias = (recordatorio.obligacion.fecha_vencimiento - timezone.localdate()).days

        if dias < 0:
            return f"«{concepto}» está vencida"
        if dias == 0:
            return f"«{concepto}» vence hoy"
        if dias == 1:
            return f"«{concepto}» vence mañana"
        return f"«{concepto}» vence en {dias} días"

    def _mensaje(self, recordatorio):
        obligacion = recordatorio.obligacion
        monto = f"{obligacion.monto:,.0f}".replace(",", ".")
        fecha = obligacion.fecha_vencimiento.strftime("%d/%m/%Y")
        return (
            f"Tu obligación «{obligacion.concepto}» por ${monto} "
            f"vence el {fecha}."
        )


class CanalEmail(Canal):
    """Correo electrónico. Previsto para después del MVP (§14)."""

    codigo = CanalNotificacion.EMAIL

    def enviar(self, recordatorio):
        raise CanalNoDisponible(
            "El canal de correo se implementa en la fase 7b. "
            "Por ahora solo está disponible la notificación en la aplicación."
        )


_REGISTRO = {
    CanalNotificacion.APP: CanalInApp(),
    CanalNotificacion.EMAIL: CanalEmail(),
}


def obtener_canal(codigo):
    canal = _REGISTRO.get(codigo)
    if canal is None:
        raise CanalNoDisponible(f"No hay un canal registrado para «{codigo}».")
    return canal


def canales_disponibles():
    """Canales realmente utilizables hoy."""
    return [CanalNotificacion.APP]
