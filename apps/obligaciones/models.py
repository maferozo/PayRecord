from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import UniqueConstraint
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ModeloBase

from .enums import AmbitoCategoria, EstadoObligacion, Prioridad
from .managers import CategoriaQuerySet, ObligacionQuerySet
from .services.estados import UMBRAL_POR_DEFECTO, calcular_estado, dias_para_vencer


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


class Obligacion(ModeloBase):
    """Obligación de pago: la entidad central de PAYRECORD (§7).

    El estado no se almacena, se deriva (decisión D3). La propiedad de los
    datos se resuelve siempre a través de `Obligacion.objects.visibles_para`.
    """

    # --- Propiedad y seguridad (decisión D1) ---
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Registrada por",
        on_delete=models.CASCADE,
        related_name="obligaciones",
    )
    empresa = models.ForeignKey(
        "usuarios.Empresa",
        verbose_name="Empresa",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="obligaciones",
        help_text="Se rellena automáticamente en las cuentas de empresa.",
    )

    # --- Datos de la obligación (§7) ---
    concepto = models.CharField("Concepto", max_length=150)
    descripcion = models.TextField("Descripción", blank=True)
    monto = models.DecimalField(
        "Valor",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    fecha_vencimiento = models.DateField("Fecha de vencimiento")
    categoria = models.ForeignKey(
        Categoria,
        verbose_name="Categoría",
        on_delete=models.PROTECT,
        related_name="obligaciones",
    )
    enlace_pago = models.URLField("Enlace de pago", max_length=500, blank=True)
    prioridad_usuario = models.CharField(
        "Prioridad",
        max_length=6,
        choices=Prioridad.choices,
        default=Prioridad.MEDIA,
    )

    # --- Pago: la fuente de verdad del estado ---
    pagada = models.BooleanField("Pagada", default=False)
    fecha_pago = models.DateField("Fecha de pago", null=True, blank=True)

    # --- Campos del escenario empresarial (§7), opcionales ---
    proveedor = models.CharField("Proveedor", max_length=150, blank=True)
    referencia = models.CharField("Referencia o número de factura", max_length=80, blank=True)

    # --- Borrado lógico (decisión D7) ---
    eliminada_en = models.DateTimeField("Eliminada en", null=True, blank=True)

    objects = ObligacionQuerySet.as_manager()

    class Meta:
        verbose_name = "Obligación"
        verbose_name_plural = "Obligaciones"
        ordering = ["fecha_vencimiento", "-monto"]
        indexes = [
            models.Index(fields=["usuario", "fecha_vencimiento"]),
            models.Index(fields=["empresa", "fecha_vencimiento"]),
            models.Index(fields=["pagada", "fecha_vencimiento"]),
        ]

    def __str__(self):
        return f"{self.concepto} ({self.monto})"

    def get_absolute_url(self):
        return reverse("obligaciones:detalle", args=[self.pk])

    # --- Estado derivado (§9) ---

    @property
    def umbral_usuario(self):
        configuracion = getattr(self.usuario, "configuracion", None)
        return configuracion.dias_proximo_vencimiento if configuracion else UMBRAL_POR_DEFECTO

    @property
    def estado_actual(self):
        """Estado calculado en Python.

        En los listados se usa la anotación SQL `estado`, que aplica la misma
        regla; este atajo es para una obligación suelta.
        """
        return calcular_estado(
            pagada=self.pagada,
            fecha_vencimiento=self.fecha_vencimiento,
            hoy=timezone.localdate(),
            umbral_dias=self.umbral_usuario,
        )

    @property
    def dias_restantes(self):
        return dias_para_vencer(self.fecha_vencimiento, timezone.localdate())

    @property
    def esta_vencida(self):
        return self.estado_actual == EstadoObligacion.VENCIDA

    # --- Operaciones ---

    def marcar_pagada(self, fecha=None):
        self.pagada = True
        self.fecha_pago = fecha or timezone.localdate()
        self.save(update_fields=["pagada", "fecha_pago", "actualizado_en"])

    def marcar_pendiente(self):
        self.pagada = False
        self.fecha_pago = None
        self.save(update_fields=["pagada", "fecha_pago", "actualizado_en"])

    def eliminar_logicamente(self):
        """Conserva la fila para no romper historial ni estadísticas (§17, §18)."""
        self.eliminada_en = timezone.now()
        self.save(update_fields=["eliminada_en", "actualizado_en"])
