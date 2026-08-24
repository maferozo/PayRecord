"""Configuración para despliegue / sustentación.

Se activa con DJANGO_SETTINGS_MODULE=config.settings.production
"""

from .base import *  # noqa: F401,F403

DEBUG = False

# --- Endurecimiento de seguridad (§28) ---

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Activar únicamente cuando el despliegue tenga HTTPS.
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)  # noqa: F405
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)  # noqa: F405
