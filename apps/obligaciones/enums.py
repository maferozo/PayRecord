from django.db import models


class AmbitoCategoria(models.TextChoices):
    """A qué tipo de usuario aplica una categoría (§8)."""

    PERSONAL = "PERSONAL", "Solo personal"
    EMPRESA = "EMPRESA", "Solo empresa"
    AMBOS = "AMBOS", "Personal y empresa"


class Prioridad(models.TextChoices):
    """Prioridad que el usuario asigna a mano (§7)."""

    BAJA = "BAJA", "Baja"
    MEDIA = "MEDIA", "Media"
    ALTA = "ALTA", "Alta"


class EstadoObligacion(models.TextChoices):
    """Estado derivado, nunca almacenado (§9, decisión D3).

    Se calcula a partir de `pagada`, `fecha_pago` y `fecha_vencimiento`.
    """

    PENDIENTE = "PENDIENTE", "Pendiente"
    PROXIMA_VENCER = "PROXIMA_VENCER", "Próxima a vencer"
    VENCIDA = "VENCIDA", "Vencida"
    PAGADA = "PAGADA", "Pagada"

    @property
    def clase_css(self):
        return f"pr-estado-{self.value.lower()}"
