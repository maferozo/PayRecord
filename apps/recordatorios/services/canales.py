"""Canales de notificación (§14).

Añadir un canal nuevo consiste en escribir una clase y registrarla. Ni el
modelo `Recordatorio` ni el generador cambian: por eso la promesa de §14
("agregar canales sin rehacer el sistema") es real y no un deseo.

Estado actual:
    APP    → implementado (notificación dentro de la aplicación)
    EMAIL  → implementado (correo real vía EMAIL_BACKEND, §14b)
    WhatsApp → fuera de alcance (§31)
"""

import logging
from abc import ABC, abstractmethod

from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse

from apps.recordatorios.enums import CanalNotificacion
from apps.recordatorios.models import Notificacion

_LOGGER = logging.getLogger(__name__)


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
    """Correo electrónico real, a través del EMAIL_BACKEND configurado (§14b).

    Solo se le pide enviar a este canal si el usuario activó "Notificaciones
    por correo" en su perfil — ver `aplicar_reglas()`, que es quien decide
    si vale la pena crear la regla de EMAIL en primer lugar.
    """

    codigo = CanalNotificacion.EMAIL

    def enviar(self, recordatorio):
        obligacion = recordatorio.obligacion
        destinatario = obligacion.usuario.email

        if not destinatario:
            # Sin destinatario no hay a dónde entregarlo: es un error real,
            # no un envío silenciosamente exitoso.
            raise CanalNoDisponible(
                f"El usuario «{obligacion.usuario}» no tiene un correo registrado."
            )

        asunto = self._asunto(recordatorio)
        cuerpo = self._cuerpo(recordatorio)

        _LOGGER.info(
            "Correo de recordatorio solicitado: obligación=%s destinatario=%s",
            obligacion.pk, destinatario,
        )

        try:
            entregados = send_mail(
                subject=asunto,
                message=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destinatario],
                fail_silently=False,
            )
        except Exception as error:
            _LOGGER.error(
                "Error al enviar el recordatorio por correo: obligación=%s "
                "destinatario=%s error=%s",
                obligacion.pk, destinatario, error,
            )
            raise

        if entregados != 1:
            # send_mail() no debería devolver esto sin lanzar una excepción
            # antes, pero si pasara, no se da por entregado sin pruebas.
            mensaje = f"El proveedor de correo no confirmó el envío (respuesta: {entregados})."
            _LOGGER.error(mensaje)
            raise CanalNoDisponible(mensaje)

        _LOGGER.info(
            "Correo de recordatorio aceptado por el proveedor: obligación=%s "
            "destinatario=%s",
            obligacion.pk, destinatario,
        )
        return True

    def _asunto(self, recordatorio):
        from django.utils import timezone

        concepto = recordatorio.obligacion.concepto
        dias = (recordatorio.obligacion.fecha_vencimiento - timezone.localdate()).days

        if dias < 0:
            return f"PayRecord: «{concepto}» está vencida"
        if dias == 0:
            return f"PayRecord: «{concepto}» vence hoy"
        if dias == 1:
            return f"PayRecord: «{concepto}» vence mañana"
        return f"PayRecord: «{concepto}» vence en {dias} días"

    def _cuerpo(self, recordatorio):
        obligacion = recordatorio.obligacion
        monto = f"{obligacion.monto:,.0f}".replace(",", ".")
        fecha = obligacion.fecha_vencimiento.strftime("%d/%m/%Y")
        saludo = obligacion.usuario.get_full_name() or obligacion.usuario.email

        enlace = ""
        if obligacion.enlace_pago:
            # PayRecord no procesa el pago: solo lleva al enlace que el
            # propio usuario guardó, igual que en el resto de la app.
            enlace = f"Enlace de pago: {obligacion.enlace_pago}\n\n"

        return (
            f"Hola {saludo},\n\n"
            f"Tu obligación «{obligacion.concepto}» por ${monto} vence el {fecha}.\n\n"
            f"{enlace}"
            "Puedes revisarla en PayRecord cuando quieras.\n\n"
            "— PayRecord"
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
    return [CanalNotificacion.APP, CanalNotificacion.EMAIL]
