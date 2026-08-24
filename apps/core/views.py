from django.shortcuts import render


def inicio(request):
    """Página pública de bienvenida.

    Se sustituirá por la redirección al dashboard cuando exista la Fase 5.
    """
    return render(request, "core/inicio.html")
