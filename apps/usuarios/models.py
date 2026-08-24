from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import ModeloBase

from .managers import UsuarioManager


class TipoUsuario(models.TextChoices):
    PERSONAL = "PERSONAL", "Personal"
    EMPRESA = "EMPRESA", "Empresa"


class Empresa(ModeloBase):
    """Pequeña empresa que agrupa usuarios y obligaciones (§26)."""

    nombre = models.CharField("Nombre o razón social", max_length=150)
    nit = models.CharField("NIT", max_length=30, unique=True, blank=True, null=True)
    telefono = models.CharField("Teléfono", max_length=30, blank=True)
    activa = models.BooleanField("Activa", default=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Usuario de PAYRECORD. Se identifica por correo electrónico (§6)."""

    email = models.EmailField("Correo electrónico", unique=True)
    nombre = models.CharField("Nombre completo", max_length=150)
    tipo_usuario = models.CharField(
        "Tipo de usuario",
        max_length=10,
        choices=TipoUsuario.choices,
        default=TipoUsuario.PERSONAL,
    )
    empresa = models.ForeignKey(
        Empresa,
        verbose_name="Empresa",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="usuarios",
    )

    is_active = models.BooleanField("Activo", default=True)
    is_staff = models.BooleanField("Acceso al panel de administración", default=False)
    date_joined = models.DateTimeField("Fecha de registro", default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} <{self.email}>"

    def get_full_name(self):
        return self.nombre

    def get_short_name(self):
        return self.nombre.split(" ")[0] if self.nombre else self.email

    @property
    def es_empresa(self):
        return self.tipo_usuario == TipoUsuario.EMPRESA

    @property
    def es_personal(self):
        return self.tipo_usuario == TipoUsuario.PERSONAL


class ConfiguracionUsuario(ModeloBase):
    """Preferencias del usuario, separadas de su identidad.

    Se crea automáticamente al registrarse (ver signals.py).
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="configuracion",
    )
    dias_proximo_vencimiento = models.PositiveSmallIntegerField(
        "Días para considerar una obligación próxima a vencer",
        default=7,
        help_text="Una obligación pasa a 'Próxima a vencer' cuando faltan estos días o menos.",
    )
    dias_recordatorio_default = models.JSONField(
        "Recordatorios por defecto (días antes)",
        default=list,
        blank=True,
        help_text="Días antes del vencimiento que se proponen al crear una obligación.",
    )
    notificaciones_app = models.BooleanField("Notificaciones en la aplicación", default=True)
    notificaciones_email = models.BooleanField("Notificaciones por correo", default=False)

    class Meta:
        verbose_name = "Configuración de usuario"
        verbose_name_plural = "Configuraciones de usuario"

    def __str__(self):
        return f"Configuración de {self.usuario.nombre}"
