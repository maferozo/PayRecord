"""Generación de los periodos mensuales de una obligación recurrente.

Mismo patrón que `apps/recordatorios/services/generacion.py`: el proceso es
**idempotente** gracias a la restricción única `uq_periodo_recurrente` de
`Obligacion`, no a una comprobación en Python. Ejecutarlo varias veces no
crea duplicados.

Una obligación "raíz" (`frecuencia=MENSUAL`, `obligacion_recurrente=None`) es
la que el usuario creó desde el formulario. A partir de ella se generan los
meses siguientes como obligaciones normales, cada una independiente: se
puede pagar, editar o eliminar sin afectar a las demás.
"""

import calendar
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.obligaciones.enums import FrecuenciaObligacion
from apps.obligaciones.models import Obligacion

# Cuántos meses hacia adelante se mantienen generados. No tiene sentido crear
# años de periodos por adelantado: alcanza con que el calendario y el
# dashboard siempre muestren los próximos meses.
MESES_ADELANTE = 3


def _indice_mes(fecha):
    """Convierte una fecha en un número entero de mes, para poder sumar y comparar."""
    return fecha.year * 12 + (fecha.month - 1)


def _fecha_del_indice(indice, dia):
    """El inverso de `_indice_mes`, ajustando `dia` si ese mes no lo tiene.

    Es aquí donde se resuelve el caso del día 31 en un mes de 30, o el 29/30/31
    en febrero: se usa el último día real de ese mes en vez de fallar.
    """
    anio, mes = divmod(indice, 12)
    mes += 1
    ultimo_dia_del_mes = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(dia, ultimo_dia_del_mes))


def _raices_activas(usuario=None):
    """Obligaciones mensuales "raíz": las que definen una serie."""
    consulta = Obligacion.objects.filter(
        frecuencia=FrecuenciaObligacion.MENSUAL,
        obligacion_recurrente__isnull=True,
        eliminada_en__isnull=True,
    )
    if usuario is not None:
        consulta = consulta.filter(usuario=usuario)
    return consulta


def _ultimo_indice_generado(raiz):
    """El mes más reciente que ya existe de esa serie (raíz incluida)."""
    ultima_fecha = (
        raiz.periodos.filter(eliminada_en__isnull=True)
        .order_by("-fecha_vencimiento")
        .values_list("fecha_vencimiento", flat=True)
        .first()
    )
    return _indice_mes(ultima_fecha or raiz.fecha_vencimiento)


def _copiar_reglas_recordatorio(raiz, periodo):
    """El periodo nuevo hereda las reglas activas de la raíz.

    Así cada mes generado programa sus propios recordatorios, sin que el
    usuario tenga que volver a marcarlos.
    """
    from apps.recordatorios.models import ConfiguracionRecordatorio

    for regla in raiz.reglas_recordatorio.filter(activa=True):
        ConfiguracionRecordatorio.objects.get_or_create(
            obligacion=periodo,
            dias_antes=regla.dias_antes,
            canal=regla.canal,
            defaults={"activa": True},
        )


def generar(hoy=None, usuario=None, meses_adelante=MESES_ADELANTE):
    """Crea los periodos mensuales que deberían existir hasta `meses_adelante`.

    Devuelve cuántos se crearon. Los que ya existían no se tocan.
    """
    hoy = hoy or timezone.localdate()
    indice_limite = _indice_mes(hoy) + meses_adelante

    creados = 0

    for raiz in _raices_activas(usuario):
        dia_objetivo = raiz.dia_pago_objetivo
        indice = _ultimo_indice_generado(raiz) + 1

        while indice <= indice_limite:
            fecha_vencimiento = _fecha_del_indice(indice, dia_objetivo)

            if raiz.fecha_fin and fecha_vencimiento > raiz.fecha_fin:
                break  # la serie ya terminó, no se generan más meses

            try:
                with transaction.atomic():
                    periodo, creado = Obligacion.objects.get_or_create(
                        obligacion_recurrente=raiz,
                        fecha_vencimiento=fecha_vencimiento,
                        defaults={
                            "usuario": raiz.usuario,
                            "empresa": raiz.empresa,
                            "concepto": raiz.concepto,
                            "descripcion": raiz.descripcion,
                            "monto": raiz.monto,
                            "categoria": raiz.categoria,
                            "enlace_pago": raiz.enlace_pago,
                            "prioridad_usuario": raiz.prioridad_usuario,
                            "proveedor": raiz.proveedor,
                            "referencia": raiz.referencia,
                            "frecuencia": FrecuenciaObligacion.MENSUAL,
                        },
                    )
            except IntegrityError:
                # Otro proceso lo creó entre la consulta y la inserción.
                indice += 1
                continue

            if creado:
                creados += 1
                _copiar_reglas_recordatorio(raiz, periodo)

            indice += 1

    return creados
