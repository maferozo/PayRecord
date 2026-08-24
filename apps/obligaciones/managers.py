from django.db import models
from django.db.models import Q

from .enums import AmbitoCategoria


class CategoriaQuerySet(models.QuerySet):
    """Punto único de decisión sobre qué categorías ve cada usuario (§28)."""

    def activas(self):
        return self.filter(activa=True)

    def predeterminadas(self):
        return self.filter(usuario__isnull=True)

    def propias_de(self, usuario):
        return self.filter(usuario=usuario)

    def del_ambito_de(self, usuario):
        """Filtra por el ámbito que corresponde al tipo de cuenta."""
        propio = (
            AmbitoCategoria.EMPRESA if usuario.es_empresa else AmbitoCategoria.PERSONAL
        )
        return self.filter(ambito__in=[propio, AmbitoCategoria.AMBOS])

    def disponibles_para(self, usuario):
        """Predeterminadas del sistema más las que ese usuario haya creado.

        Nunca devuelve categorías personalizadas de otro usuario.
        """
        return (
            self.activas()
            .del_ambito_de(usuario)
            .filter(Q(usuario__isnull=True) | Q(usuario=usuario))
        )

    def editables_por(self, usuario):
        """Solo las propias: las predeterminadas no se tocan (§8)."""
        return self.propias_de(usuario)
