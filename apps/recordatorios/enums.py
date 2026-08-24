from django.db import models


class CanalNotificacion(models.TextChoices):
    """Canales de entrega (§14).

    En el MVP solo está implementado APP. EMAIL queda declarado porque el
    modelo debe admitirlo sin migración cuando se implemente; WhatsApp queda
    explícitamente fuera de alcance.
    """

    APP = "APP", "Notificación en la aplicación"
    EMAIL = "EMAIL", "Correo electrónico"


class EstadoRecordatorio(models.TextChoices):
    """Estados de §13."""

    PENDIENTE = "PENDIENTE", "Pendiente"
    ENVIADO = "ENVIADO", "Enviado"
    CANCELADO = "CANCELADO", "Cancelado"
    ERROR = "ERROR", "Error"


# Opciones que se ofrecen al registrar una obligación (§13).
DIAS_RECORDATORIO = [
    (7, "7 días antes"),
    (3, "3 días antes"),
    (1, "1 día antes"),
    (0, "El día del vencimiento"),
]

DIAS_VALIDOS = [dias for dias, _ in DIAS_RECORDATORIO]
