from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint

from apps.core.models import ModeloBase

from .enums import AmbitoCategoria
from .managers import CategoriaQuerySet


class Categoria(ModeloBase):
    """Clasificación de una obligación (§8).

    Convive un catálogo predeterminado del sistema (usuario nulo, compartido
    por todos y no editable) con las categorías que cada usuario cree.
    """

    nombre = models.CharField("Nombre", max_length=80)
    codigo = models.SlugField(
        "Código",
        max_length=60,
        unique=True,
        null=True,
        blank=True,
        help_text="Identificador estable de las categorías predeterminadas. "
                  "Vacío en las creadas por un usuario.",
    )
    ambito = models.CharField(
        "Ámbito",
        max_length=10,
        choices=AmbitoCategoria.choices,
        default=AmbitoCategoria.AMBOS,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuario propietario",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="categorias",
        help_text="Vacío significa que es una categoría predeterminada del sistema.",
    )
    color = models.CharField("Color", max_length=7, default="#6B7280")
    icono = models.CharField("Icono", max_length=40, blank=True)
    peso_prioridad = models.PositiveSmallIntegerField(
        "Peso en el cálculo de prioridad",
        default=0,
        help_text="De 0 a 5. Aporta al puntaje de prioridad de las obligaciones (§12).",
    )
    activa = models.BooleanField("Activa", default=True)

    objects = CategoriaQuerySet.as_manager()

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["nombre"]
        constraints = [
            # Un usuario no puede tener dos categorías propias con el mismo nombre.
            # Las predeterminadas (usuario nulo) se protegen con `codigo` único.
            UniqueConstraint(
                fields=["usuario", "nombre"],
                name="uq_categoria_usuario_nombre",
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def es_predeterminada(self):
        return self.usuario_id is None
