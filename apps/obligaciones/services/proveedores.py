"""Agregación por proveedor para el escenario empresarial (§26).

Sobre la decisión D4: en el análisis se dejó `proveedor` como campo de texto
y se acordó reevaluarlo al llegar a esta fase. Tras probarlo con datos
reales, **se mantiene el campo de texto**: una tabla `Proveedor` añadiría un
CRUD y una relación para un dato que el usuario escribe una vez y rara vez
consulta por separado.

Lo que sí hacía falta era resolver la fragilidad del agrupamiento por texto
libre ("Claro" y "claro " serían dos proveedores). Se ataca por dos vías:

1. `normalizar` limpia el valor antes de guardarlo y reutiliza la grafía ya
   existente del mismo usuario, de modo que no se multipliquen variantes.
2. El formulario ofrece los proveedores ya usados como sugerencias.

Si en el futuro hicieran falta datos propios del proveedor (NIT, contacto,
condiciones de pago), entonces sí tocará la tabla.
"""

from django.db.models import Count, Max, Min, Q, Sum

from apps.obligaciones.models import Obligacion


def normalizar(nombre, usuario):
    """Limpia el nombre y reutiliza la grafía que el usuario ya usó.

    «  claro » junto a un «Claro» existente se guarda como «Claro».
    """
    nombre = " ".join((nombre or "").split())
    if not nombre:
        return ""

    existente = (
        Obligacion.objects.visibles_para(usuario)
        .filter(proveedor__iexact=nombre)
        .exclude(proveedor="")
        .values_list("proveedor", flat=True)
        .first()
    )
    return existente or nombre


def sugerencias(usuario, limite=50):
    """Proveedores que el usuario ya ha usado, para el autocompletado."""
    if not usuario.es_empresa:
        return []

    return list(
        Obligacion.objects.visibles_para(usuario)
        .exclude(proveedor="")
        .values_list("proveedor", flat=True)
        .distinct()
        .order_by("proveedor")[:limite]
    )


def resumen(usuario, hoy=None):
    """Una fila por proveedor con lo que se le debe y lo ya pagado (§26)."""
    from django.utils import timezone

    hoy = hoy or timezone.localdate()

    return list(
        Obligacion.objects.para_usuario(usuario, hoy=hoy)
        .exclude(proveedor="")
        .values("proveedor")
        .annotate(
            cantidad=Count("id"),
            total=Sum("monto"),
            pendiente=Sum("monto", filter=Q(pagada=False)),
            pagado=Sum("monto", filter=Q(pagada=True)),
            vencido=Sum("monto", filter=Q(pagada=False, fecha_vencimiento__lt=hoy)),
            proximo_vencimiento=Min("fecha_vencimiento", filter=Q(pagada=False)),
            ultima=Max("fecha_vencimiento"),
        )
        .order_by("-pendiente", "-total")
    )
