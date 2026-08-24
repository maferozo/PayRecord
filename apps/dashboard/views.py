from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from . import selectors


@login_required
def inicio(request):
    """Dashboard: la pantalla principal de PAYRECORD (§11)."""
    usuario = request.user
    hoy = timezone.localdate()

    contexto = {
        "hoy": hoy,
        "resumen": selectors.resumen(usuario, hoy),
        "prioridades": selectors.prioridades_del_dia(usuario, limite=5, hoy=hoy),
        "proximas": selectors.proximas_obligaciones(usuario, limite=6, hoy=hoy),
        "por_categoria": selectors.gasto_por_categoria(usuario, hoy=hoy),
        "proveedores": selectors.principales_proveedores(usuario, hoy=hoy),
    }
    return render(request, "dashboard/inicio.html", contexto)
