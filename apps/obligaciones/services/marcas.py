"""Reconocimiento de marca para una obligación.

Dos formas de llegar a una `Marca`:

1. **Automática** -- `detectar_marca(concepto)` reconoce el texto. Solo lo
   hace para nombres que son prácticamente inequívocos (un nombre propio
   de marca global, "Spotify", "Netflix"...). Los proveedores locales de
   celular/internet/servicios públicos (Claro, Tigo, EPM...) **no** se
   autodetectan a propósito: sus nombres se confunden más fácilmente con
   palabras comunes o entre sí, así que para esos la elección es manual.
2. **Manual** -- el usuario la elige en el formulario y queda guardada en
   `Obligacion.marca` (la clave, no el nombre visible). Eso es lo que
   consulta primero `obligaciones_extras.badge_obligacion`: una elección
   explícita del usuario siempre gana sobre lo que el texto sugiera.

Los logos reales (SVG) vienen de Simple Icons (CC0, ver
static/img/marcas/LICENCIA.md). Donde no hay un logo legítimo disponible
(la inmensa mayoría de las marcas colombianas de telecomunicaciones y
servicios públicos no están en esa librería -- se comprobó una por una,
no se asumió), se usa un glifo genérico de Bootstrap Icons -- ya vendido
en el proyecto -- con un color del propio sistema de diseño de PAYRECORD,
nunca un color de marca sin verificar.
"""

import re
import unicodedata
from dataclasses import dataclass

# Paleta ya existente del proyecto (apps/obligaciones/forms.py), reutilizada
# para las entradas sin logo propio: no se inventa un color de marca sin
# verificar, se usa un color ya elegido para PAYRECORD.
_AZUL = "#2563EB"
_CELESTE = "#0EA5E9"
_VERDE = "#10B981"
_AMBAR = "#F59E0B"
_ROJO = "#DC2626"
_MORADO = "#7C3AED"
_ROSA = "#EC4899"
_GRIS = "#6B7280"


@dataclass(frozen=True)
class Marca:
    clave: str
    nombre: str
    rubro: str  # agrupa las opciones del selector del formulario
    tipo: str  # "svg" (logo real) | "icono" (glifo de respaldo, Bootstrap Icons)
    valor: str  # ruta dentro de static/ (svg) o clase bi-* (icono)
    color: str  # hex: oficial de marca si es "svg"; del sistema de diseño si es "icono"
    auto_detectable: bool = True  # si puede reconocerse desde el texto del concepto


RUBRO_STREAMING = "Streaming y suscripciones"
RUBRO_TELECOM = "Celular e internet"
RUBRO_HOGAR = "Servicios del hogar"
RUBRO_OTRAS = "Otras obligaciones"

_REGISTRO = [
    # --- Streaming y suscripciones: nombres propios inequívocos, sí se
    # autodetectan. Orden: lo más específico antes que lo genérico, para
    # que "Apple Music" no se quede en el "Apple" a secas. ---
    # "YouTube Music" queda SOLO para no perder el logo de obligaciones ya
    # guardadas con esa marca explícita (Obligacion.marca="youtubemusic").
    # No se ofrece más para registros nuevos: auto_detectable=False hace
    # que un "YouTube Music" nuevo caiga en el "YouTube Premium" genérico.
    Marca("youtubemusic", "YouTube Music", RUBRO_STREAMING, "svg", "img/marcas/youtubemusic.svg",
          "#FF0000", auto_detectable=False),
    Marca("youtube", "YouTube Premium", RUBRO_STREAMING, "svg", "img/marcas/youtube.svg", "#FF0000"),
    Marca("applemusic", "Apple Music", RUBRO_STREAMING, "svg", "img/marcas/applemusic.svg", "#FA243C"),
    Marca("apple", "Apple", RUBRO_STREAMING, "svg", "img/marcas/apple.svg", "#000000"),
    Marca("spotify", "Spotify", RUBRO_STREAMING, "svg", "img/marcas/spotify.svg", "#1ED760"),
    Marca("netflix", "Netflix", RUBRO_STREAMING, "svg", "img/marcas/netflix.svg", "#E50914"),
    Marca("googledrive", "Google Drive", RUBRO_STREAMING, "svg", "img/marcas/googledrive.svg", "#4285F4"),
    Marca("googleone", "Google One", RUBRO_STREAMING, "icono", "bi-google", "#4285F4"),
    Marca("google", "Google", RUBRO_STREAMING, "svg", "img/marcas/google.svg", "#4285F4"),
    Marca("microsoft365", "Microsoft 365", RUBRO_STREAMING, "icono", "bi-microsoft", _AZUL),
    Marca("microsoft", "Microsoft", RUBRO_STREAMING, "icono", "bi-microsoft", _AZUL),
    Marca("amazonprime", "Amazon Prime Video", RUBRO_STREAMING, "icono", "bi-amazon", _AMBAR),
    Marca("amazon", "Amazon", RUBRO_STREAMING, "icono", "bi-amazon", _AMBAR),
    # Disney+ no está disponible en Simple Icons al momento de esta
    # implementación (se comprobó, no se asumió) -- se reconoce el nombre
    # igual, con un icono genérico en vez de un logo inventado.
    Marca("disneyplus", "Disney+", RUBRO_STREAMING, "icono", "bi-stars", _MORADO),

    # --- Celular e internet: selección manual únicamente (el formulario
    # la pregunta solo para obligaciones de este tipo, ver
    # templates/obligaciones/obligacion_form.html). Movistar sí tiene un logo real
    # (marca global, Telefónica); Claro/Tigo/WOM no existen en Simple
    # Icons -- comprobado, no asumido. ETB se deja en el registro (sin
    # ofrecerse ya en el formulario) solo para no perder el logo de
    # obligaciones que ya la tuvieran guardada. ---
    Marca("movistar", "Movistar", RUBRO_TELECOM, "svg", "img/marcas/movistar.svg", "#019DF4", auto_detectable=False),
    Marca("claro", "Claro", RUBRO_TELECOM, "icono", "bi-phone", _ROJO, auto_detectable=False),
    Marca("tigo", "Tigo", RUBRO_TELECOM, "icono", "bi-phone", _AZUL, auto_detectable=False),
    Marca("wom", "WOM", RUBRO_TELECOM, "icono", "bi-phone", _ROSA, auto_detectable=False),
    Marca("etb", "ETB", RUBRO_TELECOM, "icono", "bi-wifi", _CELESTE, auto_detectable=False),
    Marca("otro_proveedor_telecom", "Otro proveedor", RUBRO_TELECOM,
          "icono", "bi-wifi", _GRIS, auto_detectable=False),

    # --- Servicios del hogar: simplificado a EPM únicamente (Vanti, Agua,
    # Energía y Gas se quitaron a propósito -- ver docstring del módulo).
    # Se autodetecta tanto por su propio nombre como por frases genéricas
    # de "servicios del hogar/casa/públicos", que es la forma más común en
    # que la gente realmente nombra este tipo de obligación. ---
    Marca("epm", "EPM", RUBRO_HOGAR, "icono", "bi-lightning-charge", _GRIS),

    # --- Otras obligaciones: solo las que no tienen ya una categoría
    # propia del sistema (educación y créditos sí la tienen -- ver
    # apps/obligaciones/management/commands/cargar_categorias.py -- así
    # que ya quedan identificadas por su icono de categoría, sin
    # duplicar aquí la misma idea con otro nombre). ---
    Marca("gimnasio", "Gimnasio", RUBRO_OTRAS, "icono", "bi-heart-pulse", _ROSA),
    Marca("transporte", "Transporte", RUBRO_OTRAS, "icono", "bi-bus-front", _AZUL),
    Marca("seguros", "Seguros", RUBRO_OTRAS, "icono", "bi-shield-check", _MORADO),
]

# Patrones de búsqueda para las que sí se autodetectan, con \b para no
# matchear dentro de otra palabra ni confundir nombres parecidos.
_PATRONES = {
    "youtube": r"you\s*tube",
    "applemusic": r"apple\s*music",
    "apple": r"\bapple\b",
    "spotify": r"spotify",
    "netflix": r"netflix",
    "googledrive": r"google\s*drive",
    "googleone": r"google\s*one",
    "google": r"\bgoogle\b",
    "microsoft365": r"microsoft\s*365|\bms\s*365\b|office\s*365",
    "microsoft": r"\bmicrosoft\b",
    "amazonprime": r"amazon\s*prime|\bprime\s*video\b",
    "amazon": r"\bamazon\b",
    "disneyplus": r"disney\s*\+|disney\s*plus|\bdisney\b",
    # Nombre propio o, más común en la práctica, una frase genérica de
    # "pagar los servicios de la casa" -- sin mencionar agua/luz/gas por
    # separado, porque esas sí deben quedar con el icono genérico en vez
    # de asumir que son EPM (podrían ser cualquier otra empresa).
    "epm": r"\bepm\b|servicios?\s+(del\s+hogar|p[uú]blicos|de\s+la\s+casa)",
    "gimnasio": r"gimnasio|\bgym\b",
    "transporte": r"\btransporte\b",
    "seguros": r"\bseguro[s]?\b",
}

_MARCAS_POR_CLAVE = {m.clave: m for m in _REGISTRO}

# Las 5 opciones de la pregunta "¿Qué operador tienes?" -- únicamente
# celular/internet, que es el único caso donde el formulario pregunta
# algo (ver templates/obligaciones/obligacion_form.html). No es "todo lo del
# registro que sea RUBRO_TELECOM": se escoge a mano para no ofrecer ETB,
# que ya no es una opción nueva aunque siga en el registro (ver arriba).
_CLAVES_OPERADOR = ("claro", "movistar", "tigo", "wom", "otro_proveedor_telecom")


def _normalizar(texto):
    """minúsculas, sin tildes, espacios de más colapsados."""
    texto = texto or ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().strip()
    return re.sub(r"\s+", " ", texto)


def detectar_marca(concepto):
    """Devuelve la `Marca` reconocida automáticamente en `concepto`, o
    `None`. Nunca devuelve una marca con `auto_detectable=False`: esas
    solo se asignan a mano (ver `Obligacion.marca`).
    """
    normalizado = _normalizar(concepto)
    if not normalizado:
        return None

    for marca in _REGISTRO:
        if not marca.auto_detectable:
            continue
        patron = _PATRONES[marca.clave]
        if re.search(patron, normalizado):
            return marca

    return None


def obtener_marca(clave):
    """La `Marca` registrada con esa clave, o `None`."""
    return _MARCAS_POR_CLAVE.get(clave)


def opciones_operador():
    """[(clave, nombre), ...] para la pregunta "¿Qué operador tienes?".

    Es la única pregunta de selección manual que queda en el formulario
    (streaming y EPM se reconocen solos del texto; ver docstring del
    módulo) -- por eso ya no hace falta devolver nada agrupado por rubro,
    solo esta lista fija de 5 operadores.
    """
    return [(clave, _MARCAS_POR_CLAVE[clave].nombre) for clave in _CLAVES_OPERADOR]
