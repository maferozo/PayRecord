from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.obligaciones.models import Categoria, Obligacion
from apps.recordatorios.enums import CanalNotificacion, EstadoRecordatorio
from apps.recordatorios.models import (
    ConfiguracionRecordatorio,
    Notificacion,
    Recordatorio,
)
from apps.recordatorios.services.generacion import (
    aplicar_reglas,
    enviar_pendientes,
    generar,
    procesar,
    sincronizar,
)

Usuario = get_user_model()

HOY = date(2026, 8, 18)
VENCIMIENTO = date(2026, 8, 25)  # exactamente 7 días después


class BaseRecordatorios(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )

    def crear_obligacion(self, vencimiento=VENCIMIENTO, concepto="Internet",
                         pagada=False, usuario=None):
        return Obligacion.objects.create(
            usuario=usuario or self.usuario,
            concepto=concepto,
            monto=Decimal("120000"),
            fecha_vencimiento=vencimiento,
            categoria=self.categoria,
            pagada=pagada,
        )

    def crear_regla(self, obligacion, dias):
        return ConfiguracionRecordatorio.objects.create(
            obligacion=obligacion, dias_antes=dias, canal=CanalNotificacion.APP
        )


class GeneracionSegunLaEspecificacionTests(BaseRecordatorios):
    """El escenario literal de §15.

        Hoy: 18/08/2026 · Vence: 25/08/2026 · Diferencia: 7 días
        Existe recordatorio de 7 días -> generar
    """

    def test_el_ejemplo_de_la_especificacion(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)

        creados = generar(hoy=HOY)

        self.assertEqual(creados, 1)
        recordatorio = Recordatorio.objects.get()
        self.assertEqual(recordatorio.fecha_programada, HOY)
        self.assertEqual(recordatorio.dias_antes, 7)
        self.assertEqual(recordatorio.estado, EstadoRecordatorio.PENDIENTE)

    def test_los_cuatro_plazos_de_la_especificacion(self):
        """7 días, 3 días, 1 día y el día del vencimiento (§36)."""
        obligacion = self.crear_obligacion()
        for dias in (7, 3, 1, 0):
            self.crear_regla(obligacion, dias)

        # Cada aviso se genera en su propio día, no antes.
        esperados = {
            7: date(2026, 8, 18),
            3: date(2026, 8, 22),
            1: date(2026, 8, 24),
            0: date(2026, 8, 25),
        }
        for dias, fecha in esperados.items():
            with self.subTest(dias=dias):
                generar(hoy=fecha)
                self.assertTrue(
                    Recordatorio.objects.filter(dias_antes=dias, fecha_programada=fecha).exists()
                )

    def test_no_se_genera_antes_de_tiempo(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 3)

        # El aviso de 3 días toca el 22; el 18 todavía no.
        self.assertEqual(generar(hoy=HOY), 0)
        self.assertFalse(Recordatorio.objects.exists())

    def test_obligacion_ya_vencida_genera_su_aviso(self):
        """§36: caso 'obligación vencida'."""
        obligacion = self.crear_obligacion(vencimiento=date(2026, 8, 10))
        self.crear_regla(obligacion, 0)

        creados = generar(hoy=HOY)
        self.assertEqual(creados, 1)

    def test_no_inunda_con_avisos_muy_antiguos(self):
        obligacion = self.crear_obligacion(vencimiento=date(2025, 1, 10))
        self.crear_regla(obligacion, 0)

        self.assertEqual(generar(hoy=HOY), 0)


class IdempotenciaTests(BaseRecordatorios):
    """§15 y §36: 'recordatorio duplicado'."""

    def test_ejecutar_tres_veces_no_duplica(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)

        primera = generar(hoy=HOY)
        segunda = generar(hoy=HOY)
        tercera = generar(hoy=HOY)

        self.assertEqual(primera, 1)
        self.assertEqual(segunda, 0)
        self.assertEqual(tercera, 0)
        self.assertEqual(Recordatorio.objects.count(), 1)

    def test_la_base_de_datos_impide_el_duplicado(self):
        """La garantía es una restricción, no un `if` en Python."""
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)
        generar(hoy=HOY)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Recordatorio.objects.create(
                    obligacion=obligacion,
                    dias_antes=7,
                    fecha_programada=HOY,
                    canal=CanalNotificacion.APP,
                )

    def test_procesar_repetido_no_duplica_notificaciones(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)

        procesar(hoy=HOY)
        procesar(hoy=HOY)
        procesar(hoy=HOY)

        self.assertEqual(Recordatorio.objects.count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_dos_obligaciones_distintas_no_se_estorban(self):
        for concepto in ("Internet", "Arriendo"):
            obligacion = self.crear_obligacion(concepto=concepto)
            self.crear_regla(obligacion, 7)

        self.assertEqual(generar(hoy=HOY), 2)


class EnvioTests(BaseRecordatorios):

    def test_el_envio_crea_la_notificacion(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)
        generar(hoy=HOY)

        enviados, errores = enviar_pendientes(hoy=HOY)

        self.assertEqual((enviados, errores), (1, 0))
        notificacion = Notificacion.objects.get()
        self.assertEqual(notificacion.usuario, self.usuario)
        self.assertFalse(notificacion.leida)
        self.assertIn("Internet", notificacion.titulo)

    def test_el_recordatorio_queda_marcado_como_enviado(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)
        procesar(hoy=HOY)

        recordatorio = Recordatorio.objects.get()
        self.assertEqual(recordatorio.estado, EstadoRecordatorio.ENVIADO)
        self.assertIsNotNone(recordatorio.fecha_envio)

    def test_el_texto_del_aviso_describe_la_situacion_real(self):
        """El texto se calcula contra la fecha real, no contra `dias_antes`."""
        from django.utils import timezone

        hoy = timezone.localdate()
        casos = {
            0: "vence hoy",
            1: "vence mañana",
            7: "vence en 7 días",
        }
        for dias, texto in casos.items():
            with self.subTest(dias=dias):
                obligacion = self.crear_obligacion(
                    concepto=f"Servicio {dias}", vencimiento=hoy + timedelta(days=dias)
                )
                self.crear_regla(obligacion, dias)
                procesar(hoy=hoy)

                # Se filtra por concepto: en la base conviven las de las
                # demás iteraciones del bucle.
                notificacion = Notificacion.objects.get(
                    titulo__contains=f"Servicio {dias}"
                )
                self.assertIn(texto, notificacion.titulo.lower())

    def test_un_aviso_recuperado_tarde_no_dice_que_vence_manana(self):
        """Si el equipo estuvo apagado, el aviso llega con la verdad de hoy."""
        from django.utils import timezone

        hoy = timezone.localdate()
        obligacion = self.crear_obligacion(
            concepto="Energía", vencimiento=hoy - timedelta(days=3)
        )
        self.crear_regla(obligacion, 1)  # el aviso tocaba hace 4 días

        procesar(hoy=hoy)

        self.assertIn("está vencida", Notificacion.objects.first().titulo)

    def test_un_canal_no_implementado_deja_el_recordatorio_en_error(self):
        obligacion = self.crear_obligacion()
        ConfiguracionRecordatorio.objects.create(
            obligacion=obligacion, dias_antes=7, canal=CanalNotificacion.EMAIL
        )
        generar(hoy=HOY)

        enviados, errores = enviar_pendientes(hoy=HOY)

        self.assertEqual((enviados, errores), (0, 1))
        recordatorio = Recordatorio.objects.get()
        self.assertEqual(recordatorio.estado, EstadoRecordatorio.ERROR)
        self.assertIn("fase 7b", recordatorio.detalle_error)

    def test_un_canal_en_error_no_bloquea_a_los_demas(self):
        buena = self.crear_obligacion(concepto="Con app")
        self.crear_regla(buena, 7)

        mala = self.crear_obligacion(concepto="Con correo")
        ConfiguracionRecordatorio.objects.create(
            obligacion=mala, dias_antes=7, canal=CanalNotificacion.EMAIL
        )

        generar(hoy=HOY)
        enviados, errores = enviar_pendientes(hoy=HOY)

        self.assertEqual((enviados, errores), (1, 1))


class CancelacionTests(BaseRecordatorios):
    """§13: los avisos que dejan de tener sentido se cancelan."""

    def test_marcar_pagada_cancela_los_pendientes(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 0)
        self.crear_regla(obligacion, 7)
        generar(hoy=HOY)
        self.assertEqual(Recordatorio.objects.pendientes().count(), 1)

        obligacion.marcar_pagada()

        self.assertEqual(Recordatorio.objects.pendientes().count(), 0)
        self.assertEqual(
            Recordatorio.objects.filter(estado=EstadoRecordatorio.CANCELADO).count(), 1
        )

    def test_eliminar_cancela_los_pendientes(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)
        generar(hoy=HOY)

        obligacion.eliminar_logicamente()

        self.assertEqual(Recordatorio.objects.pendientes().count(), 0)

    def test_cambiar_la_fecha_cancela_los_avisos_desalineados(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)
        generar(hoy=HOY)

        obligacion.fecha_vencimiento = date(2026, 9, 30)
        obligacion.save()

        self.assertEqual(Recordatorio.objects.pendientes().count(), 0)

    def test_los_enviados_no_se_cancelan(self):
        """Un aviso ya entregado es historial: no se reescribe."""
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)
        procesar(hoy=HOY)

        obligacion.marcar_pagada()

        recordatorio = Recordatorio.objects.get()
        self.assertEqual(recordatorio.estado, EstadoRecordatorio.ENVIADO)

    def test_una_obligacion_pagada_no_genera_nuevos(self):
        obligacion = self.crear_obligacion(pagada=True)
        self.crear_regla(obligacion, 7)

        self.assertEqual(generar(hoy=HOY), 0)

    def test_pagar_entre_generacion_y_envio_cancela_el_aviso(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)
        generar(hoy=HOY)

        Obligacion.objects.filter(pk=obligacion.pk).update(pagada=True)

        enviados, _ = enviar_pendientes(hoy=HOY)
        self.assertEqual(enviados, 0)
        self.assertEqual(Notificacion.objects.count(), 0)


class AplicarReglasTests(BaseRecordatorios):
    """Lo que hace el formulario al guardar las casillas marcadas."""

    def test_crea_las_reglas_elegidas(self):
        obligacion = self.crear_obligacion()
        aplicar_reglas(obligacion, [7, 1, 0])

        activas = obligacion.reglas_recordatorio.filter(activa=True)
        self.assertEqual(set(activas.values_list("dias_antes", flat=True)), {7, 1, 0})

    def test_desmarcar_desactiva_sin_borrar(self):
        obligacion = self.crear_obligacion()
        aplicar_reglas(obligacion, [7, 3, 1])
        aplicar_reglas(obligacion, [1])

        self.assertEqual(obligacion.reglas_recordatorio.filter(activa=True).count(), 1)
        self.assertEqual(obligacion.reglas_recordatorio.count(), 3)

    def test_volver_a_marcar_reactiva(self):
        obligacion = self.crear_obligacion()
        aplicar_reglas(obligacion, [7])
        aplicar_reglas(obligacion, [])
        aplicar_reglas(obligacion, [7])

        self.assertEqual(obligacion.reglas_recordatorio.filter(activa=True).count(), 1)
        self.assertEqual(obligacion.reglas_recordatorio.count(), 1)

    def test_una_regla_desactivada_no_genera(self):
        obligacion = self.crear_obligacion()
        aplicar_reglas(obligacion, [7])
        aplicar_reglas(obligacion, [])

        self.assertEqual(generar(hoy=HOY), 0)


class AislamientoTests(BaseRecordatorios):
    """§28: los recordatorios son tan privados como las obligaciones."""

    def test_generar_para_un_usuario_no_toca_a_los_demas(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        mia = self.crear_obligacion(concepto="Mía")
        suya = self.crear_obligacion(concepto="Suya", usuario=otro)
        self.crear_regla(mia, 7)
        self.crear_regla(suya, 7)

        creados = generar(hoy=HOY, usuario=self.usuario)

        self.assertEqual(creados, 1)
        self.assertEqual(Recordatorio.objects.get().obligacion, mia)

    def test_la_notificacion_llega_a_su_dueno(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        suya = self.crear_obligacion(concepto="Suya", usuario=otro)
        self.crear_regla(suya, 7)
        procesar(hoy=HOY)

        self.assertEqual(Notificacion.objects.get().usuario, otro)
        self.assertEqual(Notificacion.objects.de(self.usuario).count(), 0)


class ComandoTests(BaseRecordatorios):

    def test_el_comando_procesa_la_fecha_indicada(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)

        call_command("generar_recordatorios", fecha="2026-08-18", verbosity=0)

        self.assertEqual(Recordatorio.objects.count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_el_comando_es_idempotente(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)

        call_command("generar_recordatorios", fecha="2026-08-18", verbosity=0)
        call_command("generar_recordatorios", fecha="2026-08-18", verbosity=0)

        self.assertEqual(Recordatorio.objects.count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_solo_generar_no_entrega(self):
        obligacion = self.crear_obligacion()
        self.crear_regla(obligacion, 7)

        call_command("generar_recordatorios", fecha="2026-08-18",
                     solo_generar=True, verbosity=0)

        self.assertEqual(Recordatorio.objects.count(), 1)
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_una_fecha_mal_escrita_da_un_error_claro(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("generar_recordatorios", fecha="18/08/2026", verbosity=0)
