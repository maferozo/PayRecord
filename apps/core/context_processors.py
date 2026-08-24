"""Datos disponibles en todas las plantillas."""


def notificaciones(request):
    """Contador de notificaciones sin leer, para el indicador del menú."""
    if not request.user.is_authenticated:
        return {}

    from apps.recordatorios.models import Notificacion

    return {
        "notificaciones_no_leidas": Notificacion.objects.de(request.user).no_leidas().count(),
    }
