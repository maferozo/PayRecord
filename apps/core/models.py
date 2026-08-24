from django.db import models


class ModeloBase(models.Model):
    """Base abstracta con marcas de tiempo, heredada por el resto de modelos."""

    creado_en = models.DateTimeField("Creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado en", auto_now=True)

    class Meta:
        abstract = True
