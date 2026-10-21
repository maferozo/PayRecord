from django.conf import settings
from django.core.checks import Warning, register

BACKEND_CONSOLA = "django.core.mail.backends.console.EmailBackend"


@register()
def revisar_backend_correo(app_configs, **kwargs):
    """Evita que producción "envíe" recordatorios que en realidad no salen.

    El backend de consola es correcto para desarrollar: no requiere
    credenciales y es rápido de ver en la terminal. El riesgo es que, si
    EMAIL_BACKEND no queda configurado en las variables de entorno del
    despliegue, producción hereda ese mismo backend sin que nadie lo note
    — los correos "se envían" sin lanzar ningún error, solo que terminan
    impresos en el log del servidor y nunca llegan a nadie.
    """
    if settings.DEBUG or settings.EMAIL_BACKEND != BACKEND_CONSOLA:
        return []

    return [
        Warning(
            "EMAIL_BACKEND sigue en el backend de consola con DEBUG=False. "
            "Los correos (recordatorios por correo, recuperación de "
            "contraseña) no se entregan de verdad: solo quedan en el log "
            "del servidor.",
            hint=(
                "Define EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend "
                "y EMAIL_HOST / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD en las "
                "variables de entorno del despliegue (en Azure: Configuración "
                "→ Configuración de la aplicación)."
            ),
            id="core.W001",
        )
    ]
