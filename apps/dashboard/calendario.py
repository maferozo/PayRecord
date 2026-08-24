"""Construcción de la vista de calendario (§24).

Se arma con el módulo `calendar` de la biblioteca estándar y una cuadrícula
CSS Grid. No se usa ninguna librería de JavaScript: son unas pocas decenas
de líneas y evita una dependencia de 300 KB para algo que el servidor puede
resolver mejor (decisión D8).

La semana empieza en lunes, como en el ejemplo de la especificación.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

DIAS_SEMANA = ["L", "M", "M", "J", "V", "S", "D"]

# El calendario de Python usa 0 para el lunes.
_CALENDARIO = calendar.Calendar(firstweekday=calendar.MONDAY)


@dataclass
class DiaCalendario:
    fecha: date
    del_mes: bool
    es_hoy: bool
    obligaciones: list = field(default_factory=list)

    @property
    def total(self):
        return sum((Decimal(o.monto) for o in self.obligaciones), Decimal("0"))

    @property
    def tiene_vencidas(self):
        return any(o.estado == "VENCIDA" for o in self.obligaciones)

    @property
    def todas_pagadas(self):
        return bool(self.obligaciones) and all(o.pagada for o in self.obligaciones)

    @property
    def colores(self):
        """Colores de categoría de las obligaciones del día, sin repetir."""
        vistos = []
        for obligacion in self.obligaciones:
            color = obligacion.categoria.color
            if color not in vistos:
                vistos.append(color)
        return vistos[:4]


def normalizar_mes(anio, mes, hoy):
    """Devuelve un (año, mes) válido. Ante cualquier basura, el mes actual."""
    try:
        anio = int(anio)
        mes = int(mes)
    except (TypeError, ValueError):
        return hoy.year, hoy.month

    if not 1 <= mes <= 12 or not 1900 <= anio <= 2200:
        return hoy.year, hoy.month

    return anio, mes


def mes_anterior(anio, mes):
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def mes_siguiente(anio, mes):
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def construir_mes(anio, mes, obligaciones, hoy):
    """Arma la cuadrícula del mes con sus obligaciones ya repartidas por día.

    `obligaciones` debe venir ya filtrada por usuario: esta función no
    consulta la base de datos ni sabe quién está mirando.
    """
    por_fecha = {}
    for obligacion in obligaciones:
        por_fecha.setdefault(obligacion.fecha_vencimiento, []).append(obligacion)

    semanas = []
    for semana in _CALENDARIO.monthdatescalendar(anio, mes):
        fila = [
            DiaCalendario(
                fecha=fecha,
                del_mes=(fecha.month == mes),
                es_hoy=(fecha == hoy),
                obligaciones=por_fecha.get(fecha, []),
            )
            for fecha in semana
        ]
        semanas.append(fila)

    return semanas


def nombre_mes(anio, mes):
    return f"{MESES[mes - 1].capitalize()} {anio}"
