"""Configuración de desarrollo."""

from .base import *  # noqa: F401,F403

DEBUG = True

INTERNAL_IPS = ["127.0.0.1"]

# EMAIL_BACKEND ya lo define base.py a partir de la variable de entorno
# (por defecto, consola: los correos se imprimen en la terminal, no se
# envían). No se repite aquí a propósito -- hacerlo de nuevo, fijo, pisaría
# cualquier EMAIL_BACKEND=...smtp... que se ponga en el .env local para
# probar el envío real.
