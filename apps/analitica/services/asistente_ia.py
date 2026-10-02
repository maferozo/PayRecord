"""PayRecord AI: asistente financiero conversacional (fase de consulta).

Arquitectura (igual a la que describe la documentación de Gemini para
function calling):

    Usuario -> PayRecord AI -> Gemini -> [decide qué herramienta usar]
            -> Backend PayRecord (consulta real) -> Gemini -> respuesta final

Gemini NUNCA toca la base de datos ni recibe toda la información del
usuario de una vez: decide qué pregunta necesita responder y llama a una de
las funciones de `_tools_lectura`, que son cierres sobre `usuario` — el
modelo no puede elegir ni inventar un usuario distinto al que hizo la
pregunta, porque `usuario` ni siquiera es un parámetro que Gemini vea.

Todas las herramientas son de SOLO LECTURA: reutilizan exactamente los
selectors que ya alimentan `/estadisticas/` y el modelo de `Obligacion`, sin
duplicar ninguna consulta ni cálculo. Crear, editar o eliminar obligaciones
desde el chat es una fase aparte, todavía no implementada aquí a propósito
(necesita un paso de confirmación que esta fase no tiene).
"""

import logging
from datetime import date

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from apps.core.templatetags.formato import moneda_cop
from apps.obligaciones.enums import EstadoObligacion
from apps.obligaciones.models import Categoria, Obligacion

# El modelo razona internamente antes de responder (y más aún cuando además
# tiene que decidir qué herramienta llamar), y ese razonamiento se descuenta
# del mismo límite de tokens que la respuesta visible. Un límite bajo corta
# la respuesta a la mitad aunque el modelo "sí sabía" cómo terminarla.
MAXIMO_TOKENS_RESPUESTA = 4096

# Cuántos turnos anteriores de la conversación se reenvían como contexto.
# Suficiente para "¿y en enero?" después de "¿cuánto debo en diciembre?",
# sin arrastrar una conversación entera (más tokens, más costo, sin
# necesidad real para este tipo de preguntas).
TURNOS_DE_HISTORIAL = 6

_LOGGER = logging.getLogger(__name__)

PREGUNTA_RESUMEN = (
    "Genera un resumen breve de mi situación financiera actual: mi mayor "
    "compromiso, mi próximo vencimiento, la categoría con más dinero "
    "comprometido y algún patrón relevante que puedas notar en los datos."
)

PROMPT_SISTEMA = """Eres PayRecord AI, el asistente financiero integrado en PayRecord, una \
aplicación de gestión de obligaciones de pago. Hoy es {fecha_larga} ({fecha_iso}).

Tienes herramientas para consultar los datos REALES del usuario. Nunca \
respondas una cifra, una fecha o el nombre de una obligación sin haber \
llamado antes a la herramienta correspondiente — no los recuerdas ni los \
calculas tú, siempre vienen de PayRecord.

Reglas estrictas, sin excepción:
- Si no tienes una herramienta que te dé el dato exacto que piden, dilo con \
claridad en vez de inventarlo o estimarlo.
- No puedes ejecutar pagos ni crear, editar o eliminar obligaciones. No \
tienes esa capacidad — nunca sugieras que sí la tienes.
- No te presentes como asesor financiero profesional ni des \
recomendaciones de inversión o de endeudamiento: solo explicas lo que ya \
está registrado.
- Responde en español, breve y directo. Los montos en pesos colombianos \
con el formato $1.234.567.
- No uses formato Markdown (nada de **negrita**, _cursiva_ ni encabezados \
con #): el texto se muestra tal cual, sin interpretar esos símbolos.
- Si la pregunta no tiene relación con las obligaciones del usuario, dilo \
con amabilidad y sugiere qué sí puedes responder — no llames a ninguna \
herramienta en ese caso.

Sobre fechas y períodos ("este mes", "próximo mes", "en febrero", "del 10 \
al 25", "próximos 30 días", "esta semana"): tú calculas fecha_inicio y \
fecha_fin en formato ISO (AAAA-MM-DD) a partir de la fecha de hoy de arriba, \
y se los pasas así a `consultar_obligaciones_por_periodo`. Si el período es \
ambiguo en el año (por ejemplo "en febrero" y podría ser el que ya pasó o \
el que viene), NO asumas uno en silencio: pregunta primero a cuál se \
refiere, a menos que el historial de la conversación ya lo haya dejado claro.

MUY IMPORTANTE — Título frente a Categoría, nunca los confundas:
Cada obligación que te devuelve una herramienta trae "titulo" y "categoria" \
por separado. El título (por ejemplo "Netflix", "Internet hogar", \
"Universidad") es el nombre real que el usuario le puso. La categoría (por \
ejemplo "Suscripciones", "Servicios", "Educación") es solo una \
clasificación. Al referirte a UNA obligación concreta, di siempre primero \
su título, nunca la categoría en su lugar; la categoría es información \
secundaria y opcional. Correcto: "Netflix — $67.000. Categoría: \
Suscripciones." Incorrecto, nunca lo hagas: "Suscripciones — $67.000." Esto \
no aplica si la pregunta es específicamente sobre categorías (por ejemplo \
"¿en qué categoría gasto más?"): ahí sí respondes con el nombre de la \
categoría, porque es lo que se pregunta.

Formato de la respuesta:
- Si la respuesta tiene un solo dato, una frase corta basta.
- Si reúne varias cifras (pendiente/pagado/vencido, o varias obligaciones), \
sepáralas en líneas cortas en vez de un párrafo, así:
  💰 Dinero pendiente
  $3.067.000

  📋 Obligaciones pendientes
  2
- Para una obligación concreta (próximo vencimiento, mayor obligación):
  📅 Tu próximo pago es Internet hogar
  $120.000
  Categoría: Servicios
  Vence el 30 de septiembre.
"""


class AsistenteError(Exception):
    """Algo impidió obtener una respuesta. El mensaje ya es apto para mostrar."""


def disponible():
    """Si hay clave configurada. La interfaz se apoya en esto para
    mostrarse desactivada en vez de fallar."""
    return bool(settings.GEMINI_API_KEY)


def _resumen_obligacion(obligacion):
    """La forma en la que una obligación concreta se le entrega a Gemini.

    Título y categoría van en claves separadas a propósito — es lo que le
    impide a Gemini confundir una con la otra al redactar la respuesta.
    """
    datos = {
        "titulo": obligacion.concepto,
        "categoria": obligacion.categoria.nombre,
        "valor": float(obligacion.monto),
        "vencimiento": obligacion.fecha_vencimiento.isoformat(),
        "estado": obligacion.estado_actual.label,
        "pagada": obligacion.pagada,
    }
    if obligacion.pagada and obligacion.fecha_pago:
        datos["fecha_pago"] = obligacion.fecha_pago.isoformat()
    return datos


def _tools_lectura(usuario, hoy):
    """Las herramientas de solo lectura que Gemini puede usar en esta
    consulta. Cada una es un cierre sobre `usuario` y `hoy`: no son
    parámetros que el modelo rellene, así que no hay forma de que Gemini
    pida o reciba datos de otra persona.

    El SDK de Gemini genera el esquema de cada herramienta a partir de sus
    anotaciones de tipo y su docstring (function calling automático), y
    ejecuta la función por su cuenta cuando el modelo decide usarla.
    """

    def obtener_resumen_financiero() -> dict:
        """Devuelve el resumen financiero general: cuánto tiene pendiente de
        pago, cuánto ya pagó, cuánto está vencido y cuántas obligaciones hay
        en cada estado. Útil para "¿cuánto debo?", "¿cuánto tengo
        pendiente?", "¿cuánto he pagado?", "¿cuánto tengo comprometido?".
        """
        from .. import selectors

        totales = selectors.totales(usuario, hoy)
        return {
            "total_pendiente": float(totales["pendiente"]),
            "total_pagado": float(totales["pagado"]),
            "total_vencido": float(totales["vencido"]),
            "obligaciones_pendientes": totales["cantidad"] - totales["cantidad_pagadas"],
            "obligaciones_pagadas": totales["cantidad_pagadas"],
            # `.estado` (anotado en SQL con el `hoy` que se le pasó a
            # `para_usuario`) y no `.estado_actual` (la propiedad en Python,
            # que siempre usa la fecha real del servidor, no la de la
            # consulta): aquí sí importa la diferencia para poder probarlo.
            "obligaciones_vencidas": Obligacion.objects.para_usuario(usuario, hoy=hoy)
            .filter(estado=EstadoObligacion.VENCIDA).count(),
        }

    def consultar_obligaciones_por_periodo(
        fecha_inicio: str, fecha_fin: str, estado: str = "", categoria: str = "",
    ) -> dict:
        """Busca las obligaciones cuya fecha de vencimiento cae entre
        fecha_inicio y fecha_fin, ambas incluidas. Por defecto solo cuenta
        las que no se han pagado (es lo que la gente quiere decir con
        "debo" o "tengo comprometido"); pasa estado="PAGADA" si preguntan
        específicamente por lo ya pagado en ese período.

        Args:
            fecha_inicio: Fecha ISO AAAA-MM-DD de inicio del período.
            fecha_fin: Fecha ISO AAAA-MM-DD de fin del período (incluida).
            estado: Opcional: PENDIENTE, PROXIMA_VENCER, VENCIDA o PAGADA.
                Vacío = todas las que no estén pagadas.
            categoria: Opcional, nombre exacto de una categoría para filtrar.
        """
        try:
            inicio = date.fromisoformat(fecha_inicio)
            fin = date.fromisoformat(fecha_fin)
        except (TypeError, ValueError):
            return {"error": "Las fechas deben venir en formato AAAA-MM-DD."}
        if fin < inicio:
            return {"error": "fecha_fin no puede ser anterior a fecha_inicio."}

        consulta = (
            Obligacion.objects.para_usuario(usuario, hoy=hoy)
            .filter(fecha_vencimiento__gte=inicio, fecha_vencimiento__lte=fin)
            .select_related("categoria")
        )

        estado = (estado or "").strip().upper()
        if estado:
            if estado not in EstadoObligacion.values:
                return {
                    "error": f"Estado no válido: {estado}.",
                    "estados_validos": list(EstadoObligacion.values),
                }
            consulta = consulta.filter(estado=estado)
        else:
            consulta = consulta.filter(pagada=False)

        if categoria:
            consulta = consulta.filter(categoria__nombre__iexact=categoria.strip())

        obligaciones = list(consulta.order_by("fecha_vencimiento")[:25])
        return {
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "total": float(sum(o.monto for o in obligaciones)),
            "cantidad": len(obligaciones),
            "obligaciones": [_resumen_obligacion(o) for o in obligaciones],
        }

    def obtener_mayor_obligacion() -> dict:
        """Devuelve la obligación sin pagar de mayor valor, con su título
        real, categoría, valor y fecha de vencimiento. Útil para "¿cuál es
        mi mayor obligación?", "¿cuál es mi mayor gasto?".
        """
        obligacion = (
            Obligacion.objects.para_usuario(usuario, hoy=hoy)
            .filter(pagada=False)
            .select_related("categoria")
            .order_by("-monto")
            .first()
        )
        if not obligacion:
            return {"existe": False}
        return {"existe": True, **_resumen_obligacion(obligacion)}

    def consultar_dinero_por_categoria() -> dict:
        """Devuelve cuánto dinero sin pagar hay comprometido en cada
        categoría, de mayor a menor. Útil para "¿en qué categoría tengo más
        dinero comprometido?", "¿cuánto tengo comprometido en educación?".
        """
        from .. import selectors

        filas = selectors.por_categoria(usuario, hoy)
        return {
            "categorias": [
                {
                    "categoria": fila["categoria__nombre"],
                    "total": float(fila["total"]),
                    "cantidad": fila["cantidad"],
                }
                for fila in filas
            ]
        }

    def obtener_categorias_disponibles() -> dict:
        """Devuelve los nombres de las categorías que existen para este
        usuario (predeterminadas del sistema más las que haya creado)."""
        nombres = list(
            Categoria.objects.disponibles_para(usuario)
            .values_list("nombre", flat=True)
        )
        return {"categorias": nombres}

    return [
        obtener_resumen_financiero,
        consultar_obligaciones_por_periodo,
        obtener_mayor_obligacion,
        consultar_dinero_por_categoria,
        obtener_categorias_disponibles,
    ]


def _cliente():
    if not disponible():
        raise ImproperlyConfigured(
            "GEMINI_API_KEY no está configurada. Ver .env.example."
        )
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _construir_contenidos(pregunta, historial):
    """Arma la lista de turnos que se le manda a Gemini: el historial
    reciente (para que "¿y en enero?" tenga sentido) y la pregunta nueva al
    final. `historial` es una lista plana de {"pregunta", "respuesta"} que
    la vista guarda en la sesión — nada de esto toca la base de datos.
    """
    contenidos = []
    for turno in (historial or [])[-TURNOS_DE_HISTORIAL:]:
        contenidos.append({"role": "user", "parts": [{"text": turno["pregunta"]}]})
        contenidos.append({"role": "model", "parts": [{"text": turno["respuesta"]}]})
    contenidos.append({"role": "user", "parts": [{"text": pregunta}]})
    return contenidos


def preguntar(usuario, pregunta, historial=None, hoy=None):
    """Responde una pregunta del usuario usando solo herramientas que
    consultan sus datos reales — nunca un bloque de contexto precalculado.

    Lanza AsistenteError con un mensaje apto para mostrar si algo falla —
    la vista no necesita saber de excepciones de la librería de Gemini, y el
    detalle técnico del error se registra en el log del servidor, nunca se
    le muestra al usuario tal cual.
    """
    hoy = hoy or timezone.localdate()
    prompt_sistema = PROMPT_SISTEMA.format(
        fecha_larga=hoy.strftime("%A %d de %B de %Y"), fecha_iso=hoy.isoformat(),
    )

    cliente = _cliente()
    config = genai_types.GenerateContentConfig(
        system_instruction=prompt_sistema,
        max_output_tokens=MAXIMO_TOKENS_RESPUESTA,
        tools=_tools_lectura(usuario, hoy),
    )
    contenidos = _construir_contenidos(pregunta, historial)

    # El nivel gratuito de Gemini se satura seguido en horas pico (503 "high
    # demand"), casi siempre pasajero. Un solo reintento, dentro de esta
    # misma consulta del usuario, no rompe la regla de "nunca llamar en
    # segundo plano": sigue siendo una llamada que el usuario pidió.
    intentos = 2
    for intento in range(1, intentos + 1):
        try:
            respuesta = cliente.models.generate_content(
                model=settings.GEMINI_MODEL, contents=contenidos, config=config,
            )
            break
        except genai_errors.APIError as error:
            _LOGGER.warning(
                "PayRecord AI: error de Gemini (código %s, intento %s/%s): %s",
                error.code, intento, intentos, error.message,
            )
            if error.code in (401, 403):
                raise AsistenteError(
                    "La clave de PayRecord AI no es válida. Revisa GEMINI_API_KEY en el .env."
                )
            if error.code == 429:
                raise AsistenteError(
                    "PayRecord AI está recibiendo muchas consultas. Intenta de nuevo en un momento."
                )
            if error.code in (500, 503) and intento < intentos:
                continue  # probablemente pasajero (alta demanda en el nivel gratuito): un reintento
            raise AsistenteError("PayRecord AI no pudo responder ahora mismo. Intenta de nuevo.")
        except Exception:  # noqa: BLE001 - errores de red u otros, nunca deben tumbar la vista
            _LOGGER.exception("PayRecord AI: fallo inesperado al llamar a Gemini")
            raise AsistenteError("No se pudo conectar con PayRecord AI. Revisa tu conexión a internet.")

    texto = (respuesta.text or "").strip()
    return texto or "No obtuve una respuesta esta vez. Intenta reformular la pregunta."


def generar_resumen(usuario, historial=None, hoy=None):
    """El botón "✨ Generar resumen financiero": la misma llamada, con una
    pregunta fija en vez de la del usuario."""
    return preguntar(usuario, PREGUNTA_RESUMEN, historial=historial, hoy=hoy)
