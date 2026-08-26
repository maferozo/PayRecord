#!/usr/bin/env bash
# Comando de arranque para Azure App Service (Linux).
#
# Se configura en el portal:
#   App Service → Configuración → Configuración general → Comando de inicio
#       bash startup.sh
#
# Azure ya ha instalado requirements.txt antes de ejecutar esto.

set -e

echo "==> Aplicando migraciones"
python manage.py migrate --noinput

echo "==> Recolectando archivos estáticos"
python manage.py collectstatic --noinput

echo "==> Cargando categorías predeterminadas (idempotente)"
python manage.py cargar_categorias

echo "==> Arrancando gunicorn"
# Azure enruta el tráfico al puerto que indica $PORT.
exec gunicorn config.wsgi:application \
    --bind=0.0.0.0:${PORT:-8000} \
    --workers=2 \
    --timeout=120 \
    --access-logfile '-' \
    --error-logfile '-'
