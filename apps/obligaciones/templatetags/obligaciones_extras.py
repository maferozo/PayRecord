"""Presentación de estados y prioridades, fuera de los templates (§35)."""

from django import template
from django.contrib.staticfiles.finders import find as encontrar_estatico
from django.utils.safestring import mark_safe

from apps.obligaciones.enums import EstadoObligacion, Prioridad
from apps.obligaciones.services.marcas import detectar_marca

register = template.Library()

_CACHE_SVG = {}


def _svg_en_linea(ruta_relativa):
    """Contenido del SVG de marca, listo para incrustar en el HTML.

    Se incrusta en vez de referenciarse con <img src="..."> o
    mask-image: así el color se controla con un solo `fill="currentColor"`
    sin depender de ninguna función CSS -- más compatible entre
    navegadores, que es justo lo que falló con mask-image (§ marcas).
    """
    if ruta_relativa in _CACHE_SVG:
        return _CACHE_SVG[ruta_relativa]

    ruta_absoluta = encontrar_estatico(ruta_relativa)
    if not ruta_absoluta:
        _CACHE_SVG[ruta_relativa] = None
        return None

    with open(ruta_absoluta, encoding="utf-8") as archivo:
        contenido = archivo.read()

    # El SVG de origen no trae fill: sin esto, el navegador lo pinta negro
    # por defecto sin importar el color de marca que se quiera usar.
    contenido = contenido.replace("<svg ", '<svg fill="currentColor" ', 1)

    _CACHE_SVG[ruta_relativa] = mark_safe(contenido)
    return _CACHE_SVG[ruta_relativa]

ICONOS_ESTADO = {
    EstadoObligacion.PENDIENTE: "bi-circle",
    EstadoObligacion.PROXIMA_VENCER: "bi-exclamation-circle",
    EstadoObligacion.VENCIDA: "bi-x-circle",
    EstadoObligacion.PAGADA: "bi-check-circle",
}


@register.filter
def etiqueta_estado(valor):
    """'VENCIDA' -> 'Vencida'"""
    try:
        return EstadoObligacion(valor).label
    except ValueError:
        return valor or ""


@register.filter
def clase_estado(valor):
    """'VENCIDA' -> 'pr-estado-vencida' (ver payrecord.css)"""
    if not valor:
        return "pr-estado-pendiente"
    return f"pr-estado-{str(valor).lower()}"


@register.filter
def icono_estado(valor):
    try:
        return ICONOS_ESTADO.get(EstadoObligacion(valor), "bi-circle")
    except ValueError:
        return "bi-circle"


@register.filter
def clase_prioridad(valor):
    """'ALTA' -> 'pr-prioridad-alta' (borde de color en la tarjeta)"""
    if not valor:
        return ""
    return f"pr-prioridad-{str(valor).lower()}"


@register.filter
def etiqueta_prioridad(valor):
    try:
        return Prioridad(valor).label
    except ValueError:
        return valor or ""


def _contexto_badge(marca, tamano, nombre_respaldo, color_respaldo, icono_respaldo):
    contexto = {
        "tamano": tamano,
        "tamano_icono": round(tamano * 0.5),
        "nombre_accesible": marca.nombre if marca else nombre_respaldo,
    }

    svg = _svg_en_linea(marca.valor) if (marca and marca.tipo == "svg") else None

    if svg:
        contexto.update({
            "tipo": "svg",
            "color": marca.color,
            "svg_contenido": svg,
        })
    elif marca and marca.tipo == "icono":
        contexto.update({
            "tipo": "icono",
            "color": marca.color,
            "clase_icono": marca.valor,
        })
    elif marca:
        # Era de tipo "svg" pero el archivo no se pudo leer: no se deja
        # la tarjeta rota, se cae a un icono genérico con el color de
        # marca (que sí se conoce igual, sin depender del archivo).
        contexto.update({
            "tipo": "icono",
            "color": marca.color,
            "clase_icono": "bi-tag",
        })
    else:
        contexto.update({
            "tipo": "icono",
            "color": color_respaldo,
            "clase_icono": icono_respaldo,
        })
    return contexto


@register.inclusion_tag("partials/badge_obligacion.html")
def badge_obligacion(obligacion, tamano=44):
    """Círculo con el logo de la obligación.

    Orden de prioridad (ver apps/obligaciones/services/marcas.py):
    1. `obligacion.marca` -- una elección explícita del usuario siempre
       gana sobre lo que el texto sugiera.
    2. Reconocimiento automático del concepto.
    3. El icono de la categoría -- el mismo respaldo que ya existía antes
       de que el reconocimiento de marca se implementara.
    """
    from apps.obligaciones.services.marcas import obtener_marca

    marca = (
        (obligacion.marca and obtener_marca(obligacion.marca))
        or detectar_marca(obligacion.concepto)
    )
    categoria = obligacion.categoria
    return _contexto_badge(
        marca, tamano,
        nombre_respaldo=categoria.nombre,
        color_respaldo=categoria.color,
        icono_respaldo=categoria.icono or "bi-tag",
    )
