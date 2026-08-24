"""Mixins de autorización.

Punto único de control para que un usuario nunca acceda a datos de otro (§28).
Las vistas de obligaciones (Fase 4) heredarán de estos mixins en lugar de
consultar los modelos directamente.
"""

from django.contrib.auth.mixins import LoginRequiredMixin


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
