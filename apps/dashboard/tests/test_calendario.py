from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.dashboard import calendario as cal
from apps.dashboard import selectors
from apps.obligaciones.models import Categoria, Obligacion

Usuario = get_user_model()


class NavegacionMesTests(SimpleTestCase):
    """Aritmética de meses, incluidos los saltos de año."""

    def test_mes_anterior(self):
        self.assertEqual(cal.mes_anterior(2026, 8), (2026, 7))

    def test_mes_anterior_cruza_el_ano(self):
        self.assertEqual(cal.mes_anterior(2026, 1), (2025, 12))

    def test_mes_siguiente(self):
        self.assertEqual(cal.mes_siguiente(2026, 8), (2026, 9))

    def test_mes_siguiente_cruza_el_ano(self):
        self.assertEqual(cal.mes_siguiente(2026, 12), (2027, 1))

    def test_nombre_del_mes_en_espanol(self):
        self.assertEqual(cal.nombre_mes(2026, 8), "Agosto 2026")
        self.assertEqual(cal.nombre_mes(2026, 12), "Diciembre 2026")


class NormalizarMesTests(SimpleTestCase):
    """Ante parámetros inválidos, el mes actual: nunca un error 500."""

    HOY = date(2026, 8, 24)

    def test_valores_correctos_se_respetan(self):
        self.assertEqual(cal.normalizar_mes(2025, 3, self.HOY), (2025, 3))

    def test_texto_de_numeros_se_admite(self):
        self.assertEqual(cal.normalizar_mes("2025", "3", self.HOY), (2025, 3))

    def test_valores_absurdos_caen_al_mes_actual(self):
        casos = [
            (2026, 13), (2026, 0), (2026, -1),
            (1500, 5), (9999, 5),
            ("abc", "def"), (None, None), ("", ""),
        ]
        for anio, mes in casos:
            with self.subTest(anio=anio, mes=mes):
                self.assertEqual(cal.normalizar_mes(anio, mes, self.HOY), (2026, 8))


class ConstruirMesTests(SimpleTestCase):

    HOY = date(2026, 8, 24)

    def test_la_cuadricula_empieza_en_lunes(self):
        semanas = cal.construir_mes(2026, 8, [], self.HOY)
        for semana in semanas:
            with self.subTest(semana=semana[0].fecha):
                self.assertEqual(semana[0].fecha.weekday(), 0)  # 0 = lunes

    def test_cada_semana_tiene_siete_dias(self):
        semanas = cal.construir_mes(2026, 8, [], self.HOY)
        for semana in semanas:
            self.assertEqual(len(semana), 7)

    def test_marca_los_dias_que_no_son_del_mes(self):
        semanas = cal.construir_mes(2026, 8, [], self.HOY)
        planos = [dia for semana in semanas for dia in semana]

        del_mes = [d for d in planos if d.del_mes]
        self.assertEqual(len(del_mes), 31)  # agosto tiene 31 días
        self.assertTrue(all(d.fecha.month == 8 for d in del_mes))

    def test_marca_el_dia_de_hoy(self):
        semanas = cal.construir_mes(2026, 8, [], self.HOY)
        planos = [dia for semana in semanas for dia in semana]
        hoy = [d for d in planos if d.es_hoy]

        self.assertEqual(len(hoy), 1)
        self.assertEqual(hoy[0].fecha, self.HOY)

    def test_febrero_bisiesto(self):
        semanas = cal.construir_mes(2028, 2, [], date(2028, 2, 1))
        planos = [d for semana in semanas for d in semana if d.del_mes]
        self.assertEqual(len(planos), 29)


class DiaCalendarioTests(TestCase):
    """Las propiedades que la plantilla usa para pintar cada celda."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.servicios = Categoria.objects.get(codigo="servicios")
        cls.creditos = Categoria.objects.get(codigo="creditos")
        cls.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )

    def crear(self, monto, fecha, pagada=False, categoria=None):
        return Obligacion.objects.create(
            usuario=self.usuario, concepto=f"O-{monto}", monto=Decimal(monto),
            fecha_vencimiento=fecha, categoria=categoria or self.servicios, pagada=pagada,
        )

    def test_suma_el_total_del_dia(self):
        fecha = date(2026, 8, 25)
        obligaciones = [self.crear(100000, fecha), self.crear(250000, fecha)]

        semanas = cal.construir_mes(2026, 8, obligaciones, date(2026, 8, 24))
        dia = next(d for s in semanas for d in s if d.fecha == fecha)

        self.assertEqual(dia.total, Decimal("350000"))
        self.assertEqual(len(dia.obligaciones), 2)

    def test_agrupa_colores_sin_repetir(self):
        fecha = date(2026, 8, 25)
        obligaciones = [
            self.crear(100000, fecha, categoria=self.servicios),
            self.crear(100000, fecha, categoria=self.servicios),
            self.crear(100000, fecha, categoria=self.creditos),
        ]

        semanas = cal.construir_mes(2026, 8, obligaciones, date(2026, 8, 24))
        dia = next(d for s in semanas for d in s if d.fecha == fecha)

        self.assertEqual(len(dia.colores), 2)

    def test_detecta_que_todo_esta_pagado(self):
        fecha = date(2026, 8, 10)
        obligaciones = [self.crear(100000, fecha, pagada=True)]

        semanas = cal.construir_mes(2026, 8, obligaciones, date(2026, 8, 24))
        dia = next(d for s in semanas for d in s if d.fecha == fecha)

        self.assertTrue(dia.todas_pagadas)

    def test_un_dia_vacio_no_esta_pagado(self):
        semanas = cal.construir_mes(2026, 8, [], date(2026, 8, 24))
        dia = next(d for s in semanas for d in s if d.fecha == date(2026, 8, 15))

        self.assertFalse(dia.todas_pagadas)
        self.assertEqual(dia.total, Decimal("0"))


class SelectoresCalendarioTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )

    def crear(self, fecha, monto=100000, usuario=None):
        return Obligacion.objects.create(
            usuario=usuario or self.usuario, concepto=f"O-{fecha}", monto=Decimal(monto),
            fecha_vencimiento=fecha, categoria=self.categoria,
        )

    def test_incluye_los_dias_visibles_de_meses_vecinos(self):
        """La cuadrícula de agosto 2026 empieza el 27 de julio."""
        self.crear(date(2026, 7, 28))
        self.crear(date(2026, 8, 15))

        obligaciones = selectors.obligaciones_del_mes(self.usuario, 2026, 8)
        self.assertEqual(len(obligaciones), 2)

    def test_excluye_lo_que_queda_fuera_de_la_cuadricula(self):
        self.crear(date(2026, 6, 10))
        self.crear(date(2026, 8, 15))

        obligaciones = selectors.obligaciones_del_mes(self.usuario, 2026, 8)
        self.assertEqual(len(obligaciones), 1)

    def test_no_devuelve_obligaciones_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear(date(2026, 8, 15), usuario=otro)

        self.assertEqual(selectors.obligaciones_del_mes(self.usuario, 2026, 8), [])

    def test_detalle_de_un_dia(self):
        self.crear(date(2026, 8, 25), monto=120000)
        self.crear(date(2026, 8, 25), monto=450000)
        self.crear(date(2026, 8, 26), monto=999999)

        obligaciones = selectors.obligaciones_del_dia(self.usuario, date(2026, 8, 25))
        self.assertEqual(len(obligaciones), 2)
        self.assertEqual(obligaciones[0].monto, Decimal("450000"))  # mayor primero

    def test_las_eliminadas_no_aparecen(self):
        obligacion = self.crear(date(2026, 8, 15))
        obligacion.eliminar_logicamente()

        self.assertEqual(selectors.obligaciones_del_mes(self.usuario, 2026, 8), [])


class VistaCalendarioTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.hoy = timezone.localdate()
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)
        self.url = reverse("dashboard:calendario")

    def crear(self, fecha, concepto="Internet", monto=120000, usuario=None):
        return Obligacion.objects.create(
            usuario=usuario or self.usuario, concepto=concepto, monto=Decimal(monto),
            fecha_vencimiento=fecha, categoria=self.categoria,
        )

    def test_responde_200_con_el_mes_actual(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "dashboard/calendario.html")
        self.assertEqual(respuesta.context["anio"], self.hoy.year)
        self.assertEqual(respuesta.context["mes"], self.hoy.month)

    def test_exige_sesion_iniciada(self):
        self.client.logout()
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/entrar/", respuesta.url)

    def test_navegar_a_otro_mes(self):
        respuesta = self.client.get(self.url, {"anio": 2027, "mes": 3})
        self.assertEqual(respuesta.context["anio"], 2027)
        self.assertEqual(respuesta.context["mes"], 3)
        self.assertContains(respuesta, "Marzo 2027")

    def test_parametros_invalidos_no_rompen(self):
        for parametros in [{"mes": 99}, {"anio": "abc"}, {"mes": ""}, {"anio": 1, "mes": 1}]:
            with self.subTest(parametros=parametros):
                respuesta = self.client.get(self.url, parametros)
                self.assertEqual(respuesta.status_code, 200)

    def test_muestra_el_detalle_del_dia_seleccionado(self):
        fecha = date(self.hoy.year, self.hoy.month, 15)
        self.crear(fecha, concepto="Recibo del agua")

        respuesta = self.client.get(
            self.url, {"anio": fecha.year, "mes": fecha.month, "dia": 15}
        )
        self.assertEqual(respuesta.context["dia_seleccionado"], fecha)
        self.assertContains(respuesta, "Recibo del agua")

    def test_un_dia_invalido_no_rompe(self):
        respuesta = self.client.get(self.url, {"dia": 99})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["dia_seleccionado"])

    def test_el_31_de_febrero_no_revienta(self):
        respuesta = self.client.get(self.url, {"anio": 2026, "mes": 2, "dia": 31})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["dia_seleccionado"])

    def test_no_muestra_obligaciones_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        fecha = date(self.hoy.year, self.hoy.month, 15)
        self.crear(fecha, concepto="Secreto ajeno", usuario=otro)

        respuesta = self.client.get(
            self.url, {"anio": fecha.year, "mes": fecha.month, "dia": 15}
        )
        self.assertNotContains(respuesta, "Secreto ajeno")

    def test_el_total_del_mes_ignora_los_dias_de_relleno(self):
        """Julio no debe sumar al total de agosto aunque se vea en la cuadrícula."""
        self.crear(date(2026, 7, 28), concepto="De julio", monto=500000)
        self.crear(date(2026, 8, 15), concepto="De agosto", monto=100000)

        respuesta = self.client.get(self.url, {"anio": 2026, "mes": 8})
        self.assertEqual(respuesta.context["total_mes"], Decimal("100000"))
        self.assertEqual(respuesta.context["cantidad_mes"], 1)
