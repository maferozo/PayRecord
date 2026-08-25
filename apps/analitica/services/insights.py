"""PAYRECORD Insights (§19).

**Esto no es inteligencia artificial y no debe presentarse como tal.** Son
observaciones derivadas por reglas de los datos reales del usuario. Cada
insight declara de dónde sale su cifra, para que sea verificable.

Diseño pensado para que §39 sea posible después sin reescribir nada:

- cada regla es una función independiente `(datos) -> Insight | None`;
- todas reciben el mismo objeto `DatosUsuario`, calculado una sola vez;
- añadir una regla es escribir una función y sumarla a `REGLAS`;
- sustituir una regla por un modelo entrenado significa cambiar esa función,
  no el módulo.

Una regla devuelve `None` cuando no tiene nada relevante que decir. Es
preferible mostrar tres observaciones útiles que diez de relleno.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum

from apps.obligaciones.models import Obligacion

# Un insight con muy pocos datos detrás no es una observación, es ruido.
MINIMO_OBLIGACIONES = 3


@dataclass(frozen=True)
class Insight:
    """Una observación concreta con su procedencia."""

    clave: str
    titulo: str
    detalle: str
    icono: str = "bi-lightbulb"
    tono: str = "neutro"  # neutro | atencion | positivo
    fuente: str = ""      # de dónde sale la cifra, para poder comprobarla


@dataclass
class DatosUsuario:
    """Todo lo que las reglas necesitan, consultado una sola vez."""

    usuario: object
    hoy: object
    obligaciones: list
    pendientes: list

    @property
    def total_pendiente(self):
        return sum((o.monto for o in self.pendientes), Decimal("0"))


def _formato_pesos(valor):
    return "$" + f"{Decimal(valor):,.0f}".replace(",", ".")


def _obligaciones(cantidad):
    """«obligación» / «obligaciones».

    No se puede concatenar un sufijo: el plural pierde la tilde.
    """
    return "obligación" if cantidad == 1 else "obligaciones"


def _dias(cantidad):
    return "día" if cantidad == 1 else "días"


# ===========================================================
#  Reglas
# ===========================================================

def regla_vencidas(datos):
    """Lo más urgente primero: lo que ya se pasó de fecha."""
    vencidas = [o for o in datos.pendientes if o.fecha_vencimiento < datos.hoy]
    if not vencidas:
        return None

    total = sum((o.monto for o in vencidas), Decimal("0"))
    cantidad = len(vencidas)
    mas_antigua = min(o.fecha_vencimiento for o in vencidas)
    dias = (datos.hoy - mas_antigua).days

    return Insight(
        clave="vencidas",
        titulo=(
            f"Tienes {cantidad} {_obligaciones(cantidad)} "
            f"vencida{'s' if cantidad > 1 else ''} por {_formato_pesos(total)}."
        ),
        detalle=f"La más antigua venció hace {dias} {_dias(dias)}.",
        icono="bi-exclamation-octagon",
        tono="atencion",
        fuente="Obligaciones sin pagar con fecha de vencimiento anterior a hoy.",
    )


def regla_proximos_siete_dias(datos):
    """El ejemplo literal de §19: cuántas vencen en la próxima semana."""
    limite = datos.hoy + timedelta(days=7)
    proximas = [
        o for o in datos.pendientes if datos.hoy <= o.fecha_vencimiento <= limite
    ]
    if not proximas:
        return None

    total = sum((o.monto for o in proximas), Decimal("0"))
    cantidad = len(proximas)

    return Insight(
        clave="proximos_7_dias",
        titulo=(
            f"Tienes {cantidad} {_obligaciones(cantidad)} que "
            f"vence{'n' if cantidad > 1 else ''} durante los próximos 7 días."
        ),
        detalle=f"Suman {_formato_pesos(total)}.",
        icono="bi-calendar-week",
        tono="atencion" if cantidad >= 3 else "neutro",
        fuente="Obligaciones sin pagar con vencimiento entre hoy y dentro de 7 días.",
    )


def regla_categoria_dominante(datos):
    """En qué categoría se concentran las obligaciones (§19)."""
    if len(datos.obligaciones) < MINIMO_OBLIGACIONES:
        return None

    conteo = {}
    for obligacion in datos.obligaciones:
        nombre = obligacion.categoria.nombre
        conteo[nombre] = conteo.get(nombre, 0) + 1

    nombre, cantidad = max(conteo.items(), key=lambda par: par[1])
    if cantidad < 2:
        return None

    porcentaje = round(cantidad * 100 / len(datos.obligaciones))

    return Insight(
        clave="categoria_dominante",
        titulo=f"Tu mayor cantidad de obligaciones se encuentra en la categoría {nombre}.",
        detalle=(
            f"Son {cantidad} de {len(datos.obligaciones)}, "
            f"un {porcentaje}% del total."
        ),
        icono="bi-tags",
        fuente="Conteo de tus obligaciones agrupadas por categoría.",
    )


def regla_categoria_mas_cara(datos):
    """Dónde se va el dinero, que no siempre coincide con dónde hay más cantidad."""
    if not datos.pendientes:
        return None

    por_categoria = {}
    cuantas = {}
    for obligacion in datos.pendientes:
        nombre = obligacion.categoria.nombre
        por_categoria[nombre] = por_categoria.get(nombre, Decimal("0")) + obligacion.monto
        cuantas[nombre] = cuantas.get(nombre, 0) + 1

    if len(por_categoria) < 2:
        return None

    nombre, total = max(por_categoria.items(), key=lambda par: par[1])

    # Si la categoría pesa por una única obligación, esto repetiría lo que ya
    # dice `regla_obligacion_mas_alta` con otras palabras.
    if cuantas[nombre] == 1:
        return None
    porcentaje = round(total * 100 / datos.total_pendiente)

    # Con tres o cuatro categorías, un 30% es el reparto natural y no dice
    # nada. Solo es una observación cuando de verdad concentra.
    if porcentaje < 45:
        return None

    return Insight(
        clave="categoria_mas_cara",
        titulo=f"{nombre} concentra el {porcentaje}% de tu dinero comprometido.",
        detalle=f"Son {_formato_pesos(total)} de {_formato_pesos(datos.total_pendiente)}.",
        icono="bi-pie-chart",
        fuente="Suma de tus obligaciones sin pagar, agrupadas por categoría.",
    )


def regla_total_del_mes(datos):
    """Cuánto hay comprometido en el mes en curso (§19)."""
    del_mes = [
        o for o in datos.pendientes
        if o.fecha_vencimiento.year == datos.hoy.year
        and o.fecha_vencimiento.month == datos.hoy.month
    ]
    if not del_mes:
        return None

    total = sum((o.monto for o in del_mes), Decimal("0"))

    return Insight(
        clave="total_mes",
        titulo=f"El valor de tus obligaciones pendientes este mes es de {_formato_pesos(total)}.",
        detalle=f"Repartidas en {len(del_mes)} {_obligaciones(len(del_mes))}.",
        icono="bi-cash-stack",
        fuente="Obligaciones sin pagar que vencen dentro del mes actual.",
    )


def regla_concentracion_de_fechas(datos):
    """Si los vencimientos se agrupan en una parte del mes (§19).

    Es la observación que permite al usuario prever los días de mayor carga.
    """
    if len(datos.obligaciones) < 4:
        return None

    dias = [o.fecha_vencimiento.day for o in datos.obligaciones]

    tramos = {
        "entre los días 1 y 10": len([d for d in dias if d <= 10]),
        "entre los días 11 y 20": len([d for d in dias if 11 <= d <= 20]),
        "entre los días 21 y 31": len([d for d in dias if d >= 21]),
    }
    tramo, cantidad = max(tramos.items(), key=lambda par: par[1])

    # Son tres tramos: la mitad justa no es concentración, es casualidad.
    porcentaje = round(cantidad * 100 / len(dias))
    if porcentaje < 60:
        return None

    return Insight(
        clave="concentracion_fechas",
        titulo=f"La mayoría de tus obligaciones vence {tramo}.",
        detalle=f"Son {cantidad} de {len(dias)}, un {porcentaje}% del total.",
        icono="bi-calendar-range",
        fuente="Día del mes de la fecha de vencimiento de todas tus obligaciones.",
    )


def regla_puntualidad(datos):
    """Cómo se ha comportado el usuario con lo que ya pagó."""
    pagadas = [
        o for o in datos.obligaciones if o.pagada and o.fecha_pago is not None
    ]
    if len(pagadas) < MINIMO_OBLIGACIONES:
        return None

    a_tiempo = [o for o in pagadas if o.fecha_pago <= o.fecha_vencimiento]
    porcentaje = round(len(a_tiempo) * 100 / len(pagadas))

    if porcentaje == 100:
        return Insight(
            clave="puntualidad",
            titulo="Has pagado a tiempo todas tus obligaciones registradas.",
            detalle=f"{len(pagadas)} de {len(pagadas)} antes o el día del vencimiento.",
            icono="bi-check-circle",
            tono="positivo",
            fuente="Comparación entre la fecha de pago y la de vencimiento.",
        )

    if porcentaje < 70:
        tarde = len(pagadas) - len(a_tiempo)
        return Insight(
            clave="puntualidad",
            titulo=f"Pagaste después del vencimiento {tarde} de {len(pagadas)} obligaciones.",
            detalle=(
                "Configurar recordatorios con más días de anticipación puede ayudarte."
            ),
            icono="bi-clock-history",
            tono="atencion",
            fuente="Comparación entre la fecha de pago y la de vencimiento.",
        )

    return Insight(
        clave="puntualidad",
        titulo=f"Pagas a tiempo el {porcentaje}% de tus obligaciones.",
        detalle=f"{len(a_tiempo)} de {len(pagadas)} antes o el día del vencimiento.",
        icono="bi-check-circle",
        tono="positivo",
        fuente="Comparación entre la fecha de pago y la de vencimiento.",
    )


def regla_obligacion_mas_alta(datos):
    """La obligación que más pesa en el presupuesto."""
    if len(datos.pendientes) < MINIMO_OBLIGACIONES:
        return None

    mayor = max(datos.pendientes, key=lambda o: o.monto)
    porcentaje = round(mayor.monto * 100 / datos.total_pendiente)

    if porcentaje < 35:
        return None

    return Insight(
        clave="obligacion_mas_alta",
        titulo=f"«{mayor.concepto}» representa el {porcentaje}% de lo que debes.",
        detalle=(
            f"{_formato_pesos(mayor.monto)} de {_formato_pesos(datos.total_pendiente)}, "
            f"con vencimiento el {mayor.fecha_vencimiento.strftime('%d/%m/%Y')}."
        ),
        icono="bi-graph-up",
        fuente="Tu obligación sin pagar de mayor valor.",
    )


def regla_sin_recordatorios(datos):
    """Obligaciones que van a vencer sin ningún aviso configurado."""
    sin_aviso = [
        o for o in datos.pendientes
        if not any(regla.activa for regla in o.reglas_recordatorio.all())
    ]
    if not sin_aviso:
        return None

    cantidad = len(sin_aviso)
    return Insight(
        clave="sin_recordatorios",
        titulo=(
            f"{cantidad} de tus obligaciones pendientes no "
            f"tiene{'n' if cantidad > 1 else ''} recordatorios configurados."
        ),
        detalle="Sin avisos, dependes de recordarlas por tu cuenta.",
        icono="bi-bell-slash",
        tono="atencion",
        fuente="Obligaciones sin pagar que no tienen ninguna regla de recordatorio activa.",
    )


# El orden importa: lo urgente arriba, el contexto después.
REGLAS = [
    regla_vencidas,
    regla_proximos_siete_dias,
    regla_total_del_mes,
    regla_obligacion_mas_alta,
    regla_categoria_mas_cara,
    regla_categoria_dominante,
    regla_concentracion_de_fechas,
    regla_sin_recordatorios,
    regla_puntualidad,
]


def construir_datos(usuario, hoy=None):
    from django.utils import timezone

    hoy = hoy or timezone.localdate()

    obligaciones = list(
        Obligacion.objects.para_usuario(usuario, hoy=hoy)
        .select_related("categoria")
        .prefetch_related("reglas_recordatorio")
    )
    return DatosUsuario(
        usuario=usuario,
        hoy=hoy,
        obligaciones=obligaciones,
        pendientes=[o for o in obligaciones if not o.pagada],
    )


def generar(usuario, hoy=None, limite=None):
    """Ejecuta todas las reglas y devuelve las que tienen algo que decir."""
    datos = construir_datos(usuario, hoy)

    if not datos.obligaciones:
        return []

    resultados = [insight for regla in REGLAS if (insight := regla(datos)) is not None]
    return resultados[:limite] if limite else resultados
