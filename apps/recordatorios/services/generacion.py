"""Generación y envío de recordatorios (§15).

El proceso es **idempotente**: ejecutarlo N veces produce exactamente el
mismo resultado que ejecutarlo una vez. Eso no se consigue con un `if not
exists` en Python —que tiene condición de carrera si el comando corre dos
veces a la vez— sino con la restricción única de `Recordatorio` y
`get_or_create`. La base de datos es la que impone la regla.

Que sea idempotente es lo que permite además dispararlo al abrir el
dashboard (catch-up), y así el usuario no pierde avisos porque su equipo
estuviera apagado a la hora de la tarea programada.
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.recordatorios.enums import EstadoRecordatorio
from apps.recordatorios.models import ConfiguracionRecordatorio, Recordatorio

from .canales import CanalNoDisponible, obtener_canal

# No se generan avisos de disparos muy antiguos: si alguien registra hoy una
# obligación vencida hace un año, no tiene sentido inundarlo de avisos.
VENTANA_RECUPERACION_DIAS = 30


def _reglas_aplicables(usuario=None):
    """Reglas activas de obligaciones vivas y sin pagar."""
    consulta = ConfiguracionRecordatorio.objects.filter(
        activa=True,
        obligacion__pagada=False,
        obligacion__eliminada_en__isnull=True,
    ).select_related("obligacion")

    if usuario is not None:
        consulta = consulta.filter(obligacion__usuario=usuario)

    return consulta


def generar(hoy=None, usuario=None, ventana_dias=VENTANA_RECUPERACION_DIAS):
    """Crea los recordatorios que ya deberían existir.

    Devuelve cuántos se crearon. Los que ya existían no se tocan.
    """
    hoy = hoy or timezone.localdate()
    limite_antiguo = hoy - timedelta(days=ventana_dias)

    creados = 0

    for regla in _reglas_aplicables(usuario):
        fecha_disparo = regla.obligacion.fecha_vencimiento - timedelta(days=regla.dias_antes)

        if fecha_disparo > hoy:
            continue  # todavía no toca
        if fecha_disparo < limite_antiguo:
            continue  # demasiado antiguo para avisar ahora

        try:
            with transaction.atomic():
                _, creado = Recordatorio.objects.get_or_create(
                    obligacion=regla.obligacion,
                    dias_antes=regla.dias_antes,
                    fecha_programada=fecha_disparo,
                    canal=regla.canal,
                    defaults={"regla": regla, "estado": EstadoRecordatorio.PENDIENTE},
                )
        except IntegrityError:
            # Otro proceso lo creó entre la consulta y la inserción.
            # La restricción única hizo su trabajo: no hay duplicado.
            continue

        if creado:
            creados += 1

    return creados


def enviar_pendientes(hoy=None, usuario=None):
    """Entrega los recordatorios pendientes cuya fecha ya llegó.

    Devuelve (enviados, errores).
    """
    hoy = hoy or timezone.localdate()

    consulta = Recordatorio.objects.vencidos(hoy).select_related(
        "obligacion", "obligacion__usuario"
    )
    if usuario is not None:
        consulta = consulta.filter(obligacion__usuario=usuario)

    enviados = errores = 0

    for recordatorio in consulta:
        # Una obligación pagada o eliminada entre la generación y el envío
        # no debe molestar al usuario.
        if recordatorio.obligacion.pagada or recordatorio.obligacion.eliminada_en:
            recordatorio.cancelar()
            continue

        try:
            canal = obtener_canal(recordatorio.canal)
            canal.enviar(recordatorio)
        except CanalNoDisponible as error:
            recordatorio.marcar_error(error)
            errores += 1
        except Exception as error:  # noqa: BLE001 - se registra y se sigue
            recordatorio.marcar_error(error)
            errores += 1
        else:
            recordatorio.marcar_enviado()
            enviados += 1

    return enviados, errores


def procesar(hoy=None, usuario=None):
    """Generar y enviar de una pasada. Es lo que ejecutan el comando y el catch-up."""
    creados = generar(hoy=hoy, usuario=usuario)
    enviados, errores = enviar_pendientes(hoy=hoy, usuario=usuario)
    return {"creados": creados, "enviados": enviados, "errores": errores}


def sincronizar(obligacion):
    """Ajusta los recordatorios pendientes de una obligación tras un cambio.

    Se llama desde una señal cuando la obligación se guarda:

    - pagada o eliminada  -> se cancela todo lo pendiente (§13)
    - cambió el vencimiento -> se cancelan los avisos que apuntaban a la
      fecha anterior; el generador creará los nuevos

    Los recordatorios ya enviados no se tocan: son historial.
    """
    pendientes = obligacion.recordatorios.pendientes()

    if obligacion.pagada or obligacion.eliminada_en:
        return pendientes.update(estado=EstadoRecordatorio.CANCELADO)

    # Fechas de disparo que siguen siendo válidas con el vencimiento actual.
    validas = {
        (
            regla.dias_antes,
            obligacion.fecha_vencimiento - timedelta(days=regla.dias_antes),
            regla.canal,
        )
        for regla in obligacion.reglas_recordatorio.filter(activa=True)
    }

    desalineados = [
        recordatorio.pk
        for recordatorio in pendientes
        if (recordatorio.dias_antes, recordatorio.fecha_programada, recordatorio.canal)
        not in validas
    ]

    if not desalineados:
        return 0

    return Recordatorio.objects.filter(pk__in=desalineados).update(
        estado=EstadoRecordatorio.CANCELADO
    )


def aplicar_reglas(obligacion, dias, canal=None):
    """Deja las reglas de la obligación exactamente en la lista `dias`.

    Se usa desde el formulario de obligaciones: el usuario marca las casillas
    y esto refleja su elección, activando, creando o desactivando reglas.
    """
    from apps.recordatorios.enums import CanalNotificacion

    canal = canal or CanalNotificacion.APP
    dias = {int(d) for d in dias}

    obligacion.reglas_recordatorio.filter(canal=canal).exclude(
        dias_antes__in=dias
    ).update(activa=False)

    for valor in dias:
        ConfiguracionRecordatorio.objects.update_or_create(
            obligacion=obligacion,
            dias_antes=valor,
            canal=canal,
            defaults={"activa": True},
        )
