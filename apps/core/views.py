from django.shortcuts import redirect, render


def inicio(request):
    """Página pública de bienvenida.

    Quien ya inició sesión no tiene nada que hacer aquí: va al dashboard.
    """
    if request.user.is_authenticated:
        return redirect("dashboard:inicio")
    return render(request, "core/inicio.html")
