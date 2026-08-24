"""Configuración de desarrollo."""

from .base import *  # noqa: F401,F403

DEBUG = True

INTERNAL_IPS = ["127.0.0.1"]

# En desarrollo los correos se imprimen en la terminal, no se envían.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
