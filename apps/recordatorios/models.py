from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

from apps.core.models import ModeloBase

from .enums import CanalNotificacion, EstadoRecordatorio


class ConfiguracionRecordatorio(ModeloBase):
    """Regla: «avísame N días antes por este canal» (§13).

    Es la intención del usuario. No es un aviso concreto: eso es Recordatorio.
    """

    obligacion = models.ForeignKey(
        "obligaciones.Obligacion",
        verbose_name="Obligación",
        on_delete=models.CASCADE,
        related_name="reglas_recordatorio",
    )
    dias_antes = models.PositiveSmallIntegerField(
        "Días antes",
        help_text="0 significa el mismo día del vencimiento.",
    )
    canal = models.CharField(
        "Canal",
        max_length=10,
        choices=CanalNotificacion.choices,
        default=CanalNotificacion.APP,
    )
    activa = models.BooleanField("Activa", default=True)

    class Meta:
        verbose_name = "Regla de recordatorio"
        verbose_name_plural = "Reglas de recordatorio"
        ordering = ["-dias_antes"]
        constraints = [
            UniqueConstraint(
                fields=["obligacion", "dias_antes", "canal"],
                name="uq_regla_recordatorio",
            ),
        ]

    def __str__(self):
        if self.dias_antes == 0:
            return f"{self.obligacion.concepto}: el día del vencimiento"
        return f"{self.obligacion.concepto}: {self.dias_antes} días antes"

    def fecha_disparo(self):
        return self.obligacion.fecha_vencimiento - timezone.timedelta(days=self.dias_antes)


class RecordatorioQuerySet(models.QuerySet):

    def pendientes(self):
        return self.filter(estado=EstadoRecordatorio.PENDIENTE)

    def enviados(self):
        return self.filter(estado=EstadoRecordatorio.ENVIADO)

    def vencidos(self, hoy=None):
        """Pendientes cuya fecha programada ya llegó."""
        hoy = hoy or timezone.localdate()
        return self.pendientes().filter(fecha_programada__lte=hoy)

    def de_usuario(self, usuario):
        return self.filter(obligacion__in=self._obligaciones_visibles(usuario))

    @staticmethod
    def _obligaciones_visibles(usuario):
        from apps.obligaciones.models import Obligacion

        return Obligacion.objects.visibles_para(usuario)


class Recordatorio(ModeloBase):
    """Aviso concreto: una regla aplicada a una fecha (§13, §15).

    La restricción única sobre (obligación, días, fecha, canal) es lo que
    garantiza la idempotencia del generador. No se apoya en una comprobación
    en Python, que sufriría condiciones de carrera si el proceso se ejecuta
    dos veces a la vez.
    """

    obligacion = models.ForeignKey(
        "obligaciones.Obligacion",
        verbose_name="Obligación",
        on_delete=models.CASCADE,
        related_name="recordatorios",
    )
    regla = models.ForeignKey(
        ConfiguracionRecordatorio,
        verbose_name="Regla que lo originó",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recordatorios",
    )
    dias_antes = models.PositiveSmallIntegerField("Días antes")
    fecha_programada = models.DateField("Fecha programada")
    canal = models.CharField(
        "Canal", max_length=10, choices=CanalNotificacion.choices,
        default=CanalNotificacion.APP,
    )
    estado = models.CharField(
        "Estado", max_length=10, choices=EstadoRecordatorio.choices,
        default=EstadoRecordatorio.PENDIENTE,
    )
    fecha_envio = models.DateTimeField("Fecha de envío", null=True, blank=True)
    detalle_error = models.TextField("Detalle del error", blank=True)

    objects = RecordatorioQuerySet.as_manager()

    class Meta:
        verbose_name = "Recordatorio"
        verbose_name_plural = "Recordatorios"
        ordering = ["fecha_programada"]
        constraints = [
            UniqueConstraint(
                fields=["obligacion", "dias_antes", "fecha_programada", "canal"],
                name="uq_recordatorio_idempotente",
            ),
        ]
        indexes = [
            models.Index(fields=["estado", "fecha_programada"]),
        ]

    def __str__(self):
        return f"{self.obligacion.concepto} · {self.fecha_programada} ({self.estado})"

    def marcar_enviado(self):
        self.estado = EstadoRecordatorio.ENVIADO
        self.fecha_envio = timezone.now()
        self.save(update_fields=["estado", "fecha_envio", "actualizado_en"])

    def marcar_error(self, detalle):
        self.estado = EstadoRecordatorio.ERROR
        self.detalle_error = str(detalle)[:2000]
        self.save(update_fields=["estado", "detalle_error", "actualizado_en"])

    def cancelar(self):
        self.estado = EstadoRecordatorio.CANCELADO
        self.save(update_fields=["estado", "actualizado_en"])


class NotificacionQuerySet(models.QuerySet):

    def de(self, usuario):
        return self.filter(usuario=usuario)

    def no_leidas(self):
        return self.filter(leida=False)


class Notificacion(ModeloBase):
    """Entrega efectiva al usuario (§14).

    Separar la entrega del recordatorio es lo que permite añadir canales sin
    tocar el generador. Además, `leida` y `fecha_lectura` son el insumo que
    necesitará §20 para saber qué recordatorios el usuario realmente consulta.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuario",
        on_delete=models.CASCADE,
        related_name="notificaciones",
    )
    recordatorio = models.ForeignKey(
        Recordatorio,
        verbose_name="Recordatorio",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notificaciones",
    )
    titulo = models.CharField("Título", max_length=150)
    mensaje = models.TextField("Mensaje")
    url_destino = models.CharField("Enlace", max_length=255, blank=True)
    leida = models.BooleanField("Leída", default=False)
    fecha_lectura = models.DateTimeField("Fecha de lectura", null=True, blank=True)

    objects = NotificacionQuerySet.as_manager()

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["usuario", "leida"]),
        ]

    def __str__(self):
        return self.titulo

    def marcar_leida(self):
        if not self.leida:
            self.leida = True
            self.fecha_lectura = timezone.now()
            self.save(update_fields=["leida", "fecha_lectura", "actualizado_en"])
