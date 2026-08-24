from django.db import models
from django.db.models import Q
from django.utils import timezone

from .enums import AmbitoCategoria, EstadoObligacion
from .services.estados import UMBRAL_POR_DEFECTO, anotacion_estado


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


class ObligacionQuerySet(models.QuerySet):
    """Acceso a obligaciones.

    `visibles_para` es el ÚNICO lugar donde se decide qué obligaciones puede
    ver un usuario (§28). Ninguna vista debe filtrar por su cuenta ni usar
    `get_object_or_404(Obligacion, pk=...)` sin pasar por aquí.
    """

    # --- Visibilidad ---

    def activas(self):
        """Excluye las eliminadas lógicamente (decisión D7)."""
        return self.filter(eliminada_en__isnull=True)

    def visibles_para(self, usuario):
        """Obligaciones propias, más las de su empresa si la tiene.

        Hoy, con un usuario por empresa, ambas condiciones coinciden. Cuando
        una empresa tenga varios usuarios (§26), esto seguirá siendo correcto
        sin tocar ninguna vista.
        """
        consulta = self.activas()
        if usuario.empresa_id:
            return consulta.filter(
                Q(usuario=usuario) | Q(empresa_id=usuario.empresa_id)
            )
        return consulta.filter(usuario=usuario)

    # --- Estado derivado ---

    def con_estado(self, hoy=None, umbral_dias=UMBRAL_POR_DEFECTO):
        """Anota `estado` en SQL para poder filtrar y ordenar por él."""
        hoy = hoy or timezone.localdate()
        return self.annotate(estado=anotacion_estado(hoy, umbral_dias))

    def para_usuario(self, usuario, hoy=None):
        """Atajo habitual: lo que ve el usuario, ya con su estado calculado.

        Usa el umbral configurado por ese usuario, no uno fijo.
        """
        umbral = UMBRAL_POR_DEFECTO
        configuracion = getattr(usuario, "configuracion", None)
        if configuracion:
            umbral = configuracion.dias_proximo_vencimiento

        return self.visibles_para(usuario).con_estado(hoy=hoy, umbral_dias=umbral)

    # --- Filtros de conveniencia ---

    def pendientes_de_pago(self):
        """Todo lo que aún no se ha pagado, sin importar si venció."""
        return self.filter(pagada=False)

    def pagadas(self):
        return self.filter(pagada=True)

    def vencidas(self, hoy=None):
        hoy = hoy or timezone.localdate()
        return self.filter(pagada=False, fecha_vencimiento__lt=hoy)

    def en_estado(self, estado):
        """Requiere haber llamado antes a `con_estado`."""
        return self.filter(estado=estado)

    def proximas(self):
        """Sin pagar, ordenadas por la fecha más cercana."""
        return self.pendientes_de_pago().order_by("fecha_vencimiento", "-monto")

    def buscar(self, texto):
        if not texto:
            return self
        return self.filter(
            Q(concepto__icontains=texto)
            | Q(descripcion__icontains=texto)
            | Q(proveedor__icontains=texto)
            | Q(referencia__icontains=texto)
        )


# Estados que se ofrecen como filtro en la interfaz.
ESTADOS_FILTRABLES = [
    (EstadoObligacion.VENCIDA, "Vencidas"),
    (EstadoObligacion.PROXIMA_VENCER, "Próximas a vencer"),
    (EstadoObligacion.PENDIENTE, "Pendientes"),
    (EstadoObligacion.PAGADA, "Pagadas"),
]
