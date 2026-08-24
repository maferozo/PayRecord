from django.db import models


class AmbitoCategoria(models.TextChoices):
    """A qué tipo de usuario aplica una categoría (§8)."""

    PERSONAL = "PERSONAL", "Solo personal"
    EMPRESA = "EMPRESA", "Solo empresa"
    AMBOS = "AMBOS", "Personal y empresa"
