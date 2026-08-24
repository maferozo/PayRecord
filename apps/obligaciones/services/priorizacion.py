"""Algoritmo de prioridades de PAYRECORD (§12).

Principios de diseño, tomados del análisis de la Fase 0:

- **Determinístico.** Las mismas entradas producen siempre la misma salida.
- **Explicable.** Devuelve los motivos en texto, no solo un número. Esto es lo
  que permite presentarlo como análisis del sistema y no como inteligencia
  artificial simulada (§19).
- **Función pura.** No consulta la base de datos: recibe la obligación y un
  contexto ya calculado. Se puede probar sin fixtures.
- **Aislado.** Vive aquí y solo aquí. Sustituirlo más adelante por un modelo
  entrenado no obliga a tocar vistas ni plantillas.

Fórmula, con techo en 100 puntos:

    puntaje = urgencia (0-55)
            + peso económico relativo (0-25)
            + preferencia del usuario (0-15)
            + criticidad de la categoría (0-5)
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from apps.obligaciones.enums import Prioridad

# --- Componente 1: urgencia temporal (0-55) ---
# Es el factor dominante: el tiempo es lo único que no se puede recuperar.
UMBRAL_ALTA = 70
UMBRAL_MEDIA = 40


def _puntos_urgencia(dias):
    if dias < -7:
        return 55, "Vencida hace más de una semana"
    if dias < 0:
        return 52, f"Vencida hace {abs(dias)} día{'s' if abs(dias) != 1 else ''}"
    if dias == 0:
        return 50, "Vence hoy"
    if dias == 1:
        return 45, "Vence mañana"
    if dias <= 3:
        return 36, f"Vence en {dias} días"
    if dias <= 7:
        return 26, f"Vence en {dias} días"
    if dias <= 15:
        return 15, f"Vence en {dias} días"
    if dias <= 30:
        return 7, f"Vence en {dias} días"
    return 2, f"Vence en {dias} días"


# --- Componente 2: peso económico relativo (0-25) ---
# Relativo a las obligaciones pendientes de ESE usuario: $500.000 no
# significan lo mismo para todo el mundo.

def _puntos_monto(monto, promedio_pendiente):
    if not promedio_pendiente or promedio_pendiente <= 0:
        return 8, None

    ratio = Decimal(monto) / Decimal(promedio_pendiente)

    if ratio >= 2:
        return 25, "Monto muy alto frente a tus obligaciones pendientes"
    if ratio >= 1:
        return 16, "Monto alto frente a tus obligaciones pendientes"
    if ratio >= Decimal("0.5"):
        return 8, None
    return 3, None


# --- Componente 3: preferencia del usuario (0-15) ---
# El usuario influye, pero no puede anular la urgencia.

PUNTOS_PREFERENCIA = {
    Prioridad.ALTA: (15, "La marcaste como prioridad alta"),
    Prioridad.MEDIA: (7, None),
    Prioridad.BAJA: (0, None),
}


@dataclass(frozen=True)
class ContextoPriorizacion:
    """Datos compartidos por todas las obligaciones de una misma consulta."""

    hoy: date
    promedio_pendiente: Decimal = Decimal("0")


@dataclass(frozen=True)
class ResultadoPrioridad:
    puntaje: int
    banda: str
    motivos: list = field(default_factory=list)

    @property
    def es_alta(self):
        return self.banda == "ALTA"

    @property
    def clase_css(self):
        return f"pr-prioridad-{self.banda.lower()}"

    @property
    def indicador(self):
        return {"ALTA": "🔴", "MEDIA": "🟡", "BAJA": "🟢"}[self.banda]


def calcular_prioridad(obligacion, contexto):
    """Devuelve el puntaje, la banda y los motivos de una obligación.

    Las obligaciones pagadas quedan fuera del cálculo: ya no requieren
    atención.
    """
    if obligacion.pagada:
        return ResultadoPrioridad(0, "BAJA", ["Ya está pagada"])

    motivos = []

    dias = (obligacion.fecha_vencimiento - contexto.hoy).days
    urgencia, motivo_urgencia = _puntos_urgencia(dias)
    motivos.append(motivo_urgencia)

    economico, motivo_monto = _puntos_monto(obligacion.monto, contexto.promedio_pendiente)
    if motivo_monto:
        motivos.append(motivo_monto)

    preferencia, motivo_preferencia = PUNTOS_PREFERENCIA.get(
        obligacion.prioridad_usuario, (7, None)
    )
    if motivo_preferencia:
        motivos.append(motivo_preferencia)

    # El peso de la categoría se lee de la base de datos, no de una lista
    # dentro del código: ajustar el algoritmo no exige tocar Python (§8).
    categoria = min(obligacion.categoria.peso_prioridad, 5)
    if categoria >= 4:
        motivos.append(f"«{obligacion.categoria.nombre}» es una categoría crítica")

    puntaje = min(urgencia + economico + preferencia + categoria, 100)

    if puntaje >= UMBRAL_ALTA:
        banda = "ALTA"
    elif puntaje >= UMBRAL_MEDIA:
        banda = "MEDIA"
    else:
        banda = "BAJA"

    return ResultadoPrioridad(puntaje=puntaje, banda=banda, motivos=motivos)


def priorizar(obligaciones, contexto):
    """Ordena una lista de obligaciones de mayor a menor prioridad.

    Devuelve pares (obligacion, resultado). No toca la base de datos: el
    llamador decide qué obligaciones entran.
    """
    evaluadas = [(o, calcular_prioridad(o, contexto)) for o in obligaciones]
    evaluadas.sort(key=lambda par: (-par[1].puntaje, par[0].fecha_vencimiento))
    return evaluadas


def construir_contexto(obligaciones_pendientes, hoy):
    """Calcula el promedio que necesita el componente económico."""
    montos = [Decimal(o.monto) for o in obligaciones_pendientes]
    promedio = sum(montos) / len(montos) if montos else Decimal("0")
    return ContextoPriorizacion(hoy=hoy, promedio_pendiente=promedio)
