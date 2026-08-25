"""Mixins de autorización.

Punto único de control para que un usuario nunca acceda a datos de otro (§28).
Las vistas de obligaciones (Fase 4) heredarán de estos mixins en lugar de
consultar los modelos directamente.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class SoloEmpresaMixin(LoginRequiredMixin):
    """Restringe una vista a las cuentas de tipo empresa (§26).

    En lugar de un 403 seco, devuelve al usuario personal al dashboard con
    una explicación: la vista no le está prohibida por permisos, es que no
    tiene sentido en su escenario.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.es_empresa:
            messages.info(
                request,
                "Esa sección está disponible solo en las cuentas de empresa.",
            )
            return redirect("dashboard:inicio")
        return super().dispatch(request, *args, **kwargs)


class PropiedadDelUsuarioMixin(LoginRequiredMixin):
    """Restringe el queryset de la vista a lo que el usuario puede ver.

    Exige que el modelo exponga un manager con el método `visibles_para`.
    """

    def get_queryset(self):
        modelo = self.model
        if not hasattr(modelo.objects, "visibles_para"):
            raise NotImplementedError(
                f"{modelo.__name__}.objects debe implementar visibles_para(usuario) "
                "para poder usarse con PropiedadDelUsuarioMixin."
            )
        return modelo.objects.visibles_para(self.request.user)
