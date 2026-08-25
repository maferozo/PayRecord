"""Configuración para despliegue / sustentación.

Se activa con DJANGO_SETTINGS_MODULE=config.settings.production

Las protecciones que dependen de HTTPS están gobernadas por variables de
entorno y vienen desactivadas por defecto: activarlas sin certificado deja
la aplicación inaccesible. Cuando el despliegue tenga HTTPS, basta con poner
`HTTPS_ACTIVO=True` en el `.env` para encender las cuatro de golpe.

`python manage.py check --deploy` no debe reportar avisos con HTTPS_ACTIVO=True.
"""

from .base import *  # noqa: F401,F403

DEBUG = False

HTTPS_ACTIVO = env.bool("HTTPS_ACTIVO", default=False)  # noqa: F405


# --- Cabeceras y protecciones que no dependen de HTTPS (§28) ---

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# La sesión caduca a las dos semanas y se renueva con cada visita.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True


# --- Protecciones que exigen HTTPS ---

SECURE_SSL_REDIRECT = HTTPS_ACTIVO
SESSION_COOKIE_SECURE = HTTPS_ACTIVO
CSRF_COOKIE_SECURE = HTTPS_ACTIVO
SECURE_HSTS_SECONDS = 31536000 if HTTPS_ACTIVO else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS_ACTIVO
SECURE_HSTS_PRELOAD = HTTPS_ACTIVO


# --- Registro de errores ---

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "consola": {"class": "logging.StreamHandler"},
        "archivo": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "payrecord.log",  # noqa: F405
            "encoding": "utf-8",
        },
    },
    "root": {"handlers": ["consola", "archivo"], "level": "WARNING"},
}
