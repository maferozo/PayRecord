"""Configuración común a todos los entornos de PAYRECORD."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Azure App Service publica el dominio de la aplicación en esta variable.
# Se añade sola para no tener que recordar editar ALLOWED_HOSTS al desplegar.
_dominio_azure = env("WEBSITE_HOSTNAME", default="")
CSRF_TRUSTED_ORIGINS = []

if _dominio_azure:
    ALLOWED_HOSTS.append(_dominio_azure)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_dominio_azure}")

CSRF_TRUSTED_ORIGINS += env.list("CSRF_TRUSTED_ORIGINS", default=[])


# --- Aplicaciones ---

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
]

LOCAL_APPS = [
    "apps.core",
    "apps.usuarios",
    "apps.obligaciones",
    "apps.recordatorios",
    "apps.dashboard",
    "apps.analitica",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise sirve los archivos estáticos sin necesitar un servidor web
    # aparte. Va justo después de SecurityMiddleware, como pide su manual.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.notificaciones",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Base de datos ---
# Se elige el motor por variable de entorno para poder desarrollar antes de
# tener credenciales de MySQL sin tocar una línea de código (ver docs/00-analisis-fase0.md).


def _opciones_mysql():
    """Opciones de conexión a MySQL.

    Azure Database for MySQL exige TLS. En local no hace falta, así que se
    activa solo cuando se indica `DB_SSL=True`.
    """
    opciones = {
        "charset": "utf8mb4",
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    }

    if env.bool("DB_SSL", default=False):
        certificado = env("DB_SSL_CA", default="")
        # Con certificado se verifica la identidad del servidor; sin él, la
        # conexión sigue cifrada pero no se comprueba contra quién.
        opciones["ssl"] = {"ca": certificado} if certificado else {}
        if not certificado:
            opciones["ssl_mode"] = "REQUIRED"

    return opciones

if env("DB_ENGINE", default="mysql") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST", default="127.0.0.1"),
            "PORT": env("DB_PORT", default="3306"),
            "OPTIONS": _opciones_mysql(),
        }
    }


# --- Autenticación (§6) ---
# AUTH_USER_MODEL se define antes de la primera migración y no debe cambiarse
# después: hacerlo obligaría a reconstruir la base de datos (riesgo R14).

AUTH_USER_MODEL = "usuarios.Usuario"

LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "dashboard:inicio"
LOGOUT_REDIRECT_URL = "core:inicio"

PASSWORD_RESET_TIMEOUT = 60 * 60 * 24  # el enlace de recuperación dura 24 horas


# --- Contraseñas (§6, §28) ---

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Localización ---

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True


# --- Archivos estáticos y media ---

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# En producción se activa el almacenamiento comprimido de WhiteNoise
# (ver production.py). Aquí no, porque exige haber ejecutado collectstatic
# y rompería el servidor de desarrollo.

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Formularios ---

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# --- Correo (§6 recuperación de contraseña) ---

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-responder@payrecord.local")


# --- Reglas de negocio de PAYRECORD ---

DIAS_PROXIMO_VENCIMIENTO_DEFAULT = env.int("DIAS_PROXIMO_VENCIMIENTO_DEFAULT", default=7)
