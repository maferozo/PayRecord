from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.obligaciones.enums import EstadoObligacion
from apps.obligaciones.models import Categoria, Obligacion
from apps.obligaciones.services.estados import calcular_estado, dias_para_vencer

Usuario = get_user_model()

HOY = date(2026, 8, 24)


class CalcularEstadoTests(SimpleTestCase):
    """Las cuatro reglas de §9. Sin base de datos: función pura."""

    def test_pagada_manda_sobre_cualquier_fecha(self):
        # Aunque venciera hace un año, si está pagada está pagada.
        estado = calcular_estado(True, HOY - timedelta(days=365), hoy=HOY)
        self.assertEqual(estado, EstadoObligacion.PAGADA)

    def test_vencida_cuando_la_fecha_ya_paso(self):
        estado = calcular_estado(False, HOY - timedelta(days=1), hoy=HOY)
        self.assertEqual(estado, EstadoObligacion.VENCIDA)

    def test_vence_hoy_todavia_no_esta_vencida(self):
        """El día del vencimiento aún se puede pagar."""
        estado = calcular_estado(False, HOY, hoy=HOY)
        self.assertEqual(estado, EstadoObligacion.PROXIMA_VENCER)

    def test_proxima_a_vencer_dentro_del_umbral(self):
        for dias in (1, 3, 7):
            with self.subTest(dias=dias):
                estado = calcular_estado(False, HOY + timedelta(days=dias), hoy=HOY, umbral_dias=7)
                self.assertEqual(estado, EstadoObligacion.PROXIMA_VENCER)

    def test_pendiente_mas_alla_del_umbral(self):
        estado = calcular_estado(False, HOY + timedelta(days=8), hoy=HOY, umbral_dias=7)
        self.assertEqual(estado, EstadoObligacion.PENDIENTE)

    def test_el_umbral_es_configurable(self):
        """Con umbral de 15 días, algo a 10 días ya es 'próxima a vencer'."""
        fecha = HOY + timedelta(days=10)
        self.assertEqual(
            calcular_estado(False, fecha, hoy=HOY, umbral_dias=7),
            EstadoObligacion.PENDIENTE,
        )
        self.assertEqual(
            calcular_estado(False, fecha, hoy=HOY, umbral_dias=15),
            EstadoObligacion.PROXIMA_VENCER,
        )

    def test_dias_para_vencer(self):
        self.assertEqual(dias_para_vencer(HOY + timedelta(days=5), HOY), 5)
        self.assertEqual(dias_para_vencer(HOY, HOY), 0)
        self.assertEqual(dias_para_vencer(HOY - timedelta(days=3), HOY), -3)


class EstadoEnSqlTests(TestCase):
    """La anotación SQL debe coincidir con el cálculo en Python (decisión D3)."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def crear(self, dias, pagada=False):
        return Obligacion.objects.create(
            usuario=self.usuario,
            concepto=f"Obligación {dias}",
            monto=100000,
            fecha_vencimiento=HOY + timedelta(days=dias),
            categoria=self.categoria,
            pagada=pagada,
        )

    def test_sql_y_python_coinciden(self):
        casos = [(-10, False), (-1, False), (0, False), (3, False), (30, False), (5, True)]
        for dias, pagada in casos:
            self.crear(dias, pagada)

        consulta = Obligacion.objects.visibles_para(self.usuario).con_estado(
            hoy=HOY, umbral_dias=7
        )
        for obligacion in consulta:
            with self.subTest(concepto=obligacion.concepto):
                esperado = calcular_estado(
                    obligacion.pagada, obligacion.fecha_vencimiento, hoy=HOY, umbral_dias=7
                )
                self.assertEqual(obligacion.estado, esperado)

    def test_se_puede_filtrar_por_estado_en_la_base_de_datos(self):
        self.crear(-5)   # vencida
        self.crear(2)    # próxima
        self.crear(60)   # pendiente
        self.crear(3, pagada=True)

        consulta = Obligacion.objects.visibles_para(self.usuario).con_estado(
            hoy=HOY, umbral_dias=7
        )
        self.assertEqual(consulta.en_estado(EstadoObligacion.VENCIDA).count(), 1)
        self.assertEqual(consulta.en_estado(EstadoObligacion.PROXIMA_VENCER).count(), 1)
        self.assertEqual(consulta.en_estado(EstadoObligacion.PENDIENTE).count(), 1)
        self.assertEqual(consulta.en_estado(EstadoObligacion.PAGADA).count(), 1)

    def test_el_umbral_del_usuario_se_respeta(self):
        self.crear(10)
        configuracion = self.usuario.configuracion
        configuracion.dias_proximo_vencimiento = 15
        configuracion.save()
        self.usuario.refresh_from_db()

        consulta = Obligacion.objects.para_usuario(self.usuario, hoy=HOY)
        self.assertEqual(consulta.first().estado, EstadoObligacion.PROXIMA_VENCER)
