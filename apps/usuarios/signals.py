from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ConfiguracionUsuario


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_configuracion_usuario(sender, instance, created, **kwargs):
    """Todo usuario nuevo nace con su configuración por defecto.

    Se hace por señal y no en el formulario de registro para que también
    aplique a los usuarios creados desde el admin o por createsuperuser.
    """
    if created:
        ConfiguracionUsuario.objects.get_or_create(
            usuario=instance,
            defaults={
                "dias_proximo_vencimiento": settings.DIAS_PROXIMO_VENCIMIENTO_DEFAULT,
                "dias_recordatorio_default": [7, 3, 1, 0],
            },
        )
