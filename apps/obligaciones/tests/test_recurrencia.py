from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.obligaciones.enums import FrecuenciaObligacion
from apps.obligaciones.models import Categoria, Obligacion
from apps.obligaciones.services.recurrencia import generar
from apps.recordatorios.enums import CanalNotificacion
from apps.recordatorios.models import ConfiguracionRecordatorio

Usuario = get_user_model()


class BaseRecurrencia(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )

    def crear_raiz(self, vencimiento, frecuencia=FrecuenciaObligacion.MENSUAL,
                    fecha_fin=None, concepto="Internet"):
        return Obligacion.objects.create(
            usuario=self.usuario,
            concepto=concepto,
            monto=Decimal("100000"),
            fecha_vencimiento=vencimiento,
            categoria=self.categoria,
            frecuencia=frecuencia,
            fecha_fin=fecha_fin,
        )


class GenerarPeriodosTests(BaseRecurrencia):
    """El escenario literal del pedido: Internet, día 15, mensual."""

    def test_una_obligacion_unica_no_genera_periodos(self):
        self.crear_raiz(date(2026, 9, 30), frecuencia=FrecuenciaObligacion.UNICA)

        creados = generar(hoy=date(2026, 9, 7))

        self.assertEqual(creados, 0)
        self.assertEqual(Obligacion.objects.count(), 1)

    def test_genera_los_siguientes_meses(self):
        raiz = self.crear_raiz(date(2026, 9, 15))

        creados = generar(hoy=date(2026, 9, 7), meses_adelante=3)

        # sept (la raíz, ya existe) + oct, nov, dic generados = 3 nuevos
        self.assertEqual(creados, 3)
        fechas = list(
            raiz.periodos.order_by("fecha_vencimiento").values_list(
                "fecha_vencimiento", flat=True
            )
        )
        self.assertEqual(
            fechas, [date(2026, 10, 15), date(2026, 11, 15), date(2026, 12, 15)]
        )

    def test_no_duplica_si_se_ejecuta_dos_veces(self):
        self.crear_raiz(date(2026, 9, 15))

        generar(hoy=date(2026, 9, 7), meses_adelante=3)
        segunda_vez = generar(hoy=date(2026, 9, 7), meses_adelante=3)

        self.assertEqual(segunda_vez, 0)
        self.assertEqual(Obligacion.objects.count(), 4)  # raíz + 3 meses

    def test_dia_31_cae_en_el_ultimo_dia_de_meses_cortos(self):
        raiz = self.crear_raiz(date(2026, 8, 31), concepto="Arriendo")

        generar(hoy=date(2026, 8, 20), meses_adelante=6)

        fechas = list(
            raiz.periodos.order_by("fecha_vencimiento").values_list(
                "fecha_vencimiento", flat=True
            )
        )
        # sept (30), oct (31), nov (30), dic (31), ene (31), feb 2027 (28)
        self.assertEqual(fechas, [
            date(2026, 9, 30), date(2026, 10, 31), date(2026, 11, 30),
            date(2026, 12, 31), date(2027, 1, 31), date(2027, 2, 28),
        ])

    def test_respeta_fecha_fin(self):
        raiz = self.crear_raiz(date(2026, 9, 15), fecha_fin=date(2026, 11, 20))

        generar(hoy=date(2026, 9, 7), meses_adelante=6)

        fechas = list(
            raiz.periodos.order_by("fecha_vencimiento").values_list(
                "fecha_vencimiento", flat=True
            )
        )
        # noviembre 15 sí entra (antes del 20), diciembre 15 ya no
        self.assertEqual(fechas, [date(2026, 10, 15), date(2026, 11, 15)])

    def test_cada_periodo_es_independiente(self):
        raiz = self.crear_raiz(date(2026, 9, 15))
        generar(hoy=date(2026, 9, 7), meses_adelante=2)

        octubre = raiz.periodos.get(fecha_vencimiento=date(2026, 10, 15))
        octubre.marcar_pagada()

        raiz.refresh_from_db()
        noviembre = raiz.periodos.get(fecha_vencimiento=date(2026, 11, 15))
        self.assertFalse(raiz.pagada)
        self.assertFalse(noviembre.pagada)
        self.assertTrue(octubre.pagada)

    def test_copia_las_reglas_de_recordatorio_de_la_raiz(self):
        raiz = self.crear_raiz(date(2026, 9, 15))
        ConfiguracionRecordatorio.objects.create(
            obligacion=raiz, dias_antes=7, canal=CanalNotificacion.APP
        )
        ConfiguracionRecordatorio.objects.create(
            obligacion=raiz, dias_antes=1, canal=CanalNotificacion.APP
        )

        generar(hoy=date(2026, 9, 7), meses_adelante=1)

        octubre = raiz.periodos.get(fecha_vencimiento=date(2026, 10, 15))
        dias = set(
            octubre.reglas_recordatorio.filter(activa=True).values_list(
                "dias_antes", flat=True
            )
        )
        self.assertEqual(dias, {7, 1})

    def test_solo_genera_lo_de_su_propio_usuario(self):
        otro_usuario = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear_raiz(date(2026, 9, 15))
        otra_raiz = Obligacion.objects.create(
            usuario=otro_usuario, concepto="Netflix", monto=Decimal("30000"),
            fecha_vencimiento=date(2026, 9, 20), categoria=self.categoria,
            frecuencia=FrecuenciaObligacion.MENSUAL,
        )

        generar(hoy=date(2026, 9, 7), usuario=self.usuario, meses_adelante=1)

        self.assertEqual(otra_raiz.periodos.count(), 0)
