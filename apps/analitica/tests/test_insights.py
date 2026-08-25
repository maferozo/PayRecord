from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.analitica.services import insights
from apps.obligaciones.models import Categoria, Obligacion
from apps.recordatorios.services.generacion import aplicar_reglas

Usuario = get_user_model()

HOY = date(2026, 8, 24)


class BaseInsights(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.servicios = Categoria.objects.get(codigo="servicios")
        cls.creditos = Categoria.objects.get(codigo="creditos")
        cls.vivienda = Categoria.objects.get(codigo="vivienda")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)

    def crear(self, concepto, monto, dias, categoria=None, pagada=False,
              fecha_pago=None, dia_fijo=None):
        vencimiento = HOY + timedelta(days=dias)
        if dia_fijo:
            vencimiento = vencimiento.replace(day=dia_fijo)

        return Obligacion.objects.create(
            usuario=self.usuario,
            concepto=concepto,
            monto=Decimal(monto),
            fecha_vencimiento=vencimiento,
            categoria=categoria or self.servicios,
            pagada=pagada,
            fecha_pago=fecha_pago,
        )

    def claves(self, **kwargs):
        return {i.clave for i in insights.generar(self.usuario, HOY, **kwargs)}

    def por_clave(self, clave):
        for insight in insights.generar(self.usuario, HOY):
            if insight.clave == clave:
                return insight
        return None


class SinDatosTests(BaseInsights):

    def test_sin_obligaciones_no_hay_insights(self):
        self.assertEqual(insights.generar(self.usuario, HOY), [])

    def test_una_sola_obligacion_no_dispara_reglas_de_patron(self):
        """No se inventan patrones con un dato."""
        self.crear("Internet", 120000, 5)
        claves = self.claves()

        self.assertNotIn("categoria_dominante", claves)
        self.assertNotIn("concentracion_fechas", claves)
        self.assertNotIn("puntualidad", claves)


class ReglaVencidasTests(BaseInsights):

    def test_detecta_las_vencidas(self):
        self.crear("Energía", 185000, -4)
        self.crear("Agua", 74500, -10)

        insight = self.por_clave("vencidas")
        self.assertIsNotNone(insight)
        self.assertIn("2 obligaciones vencidas", insight.titulo)
        self.assertIn("$259.500", insight.titulo)
        self.assertIn("hace 10 días", insight.detalle)
        self.assertEqual(insight.tono, "atencion")

    def test_singular_con_una_sola(self):
        self.crear("Energía", 185000, -1)
        insight = self.por_clave("vencidas")
        self.assertIn("1 obligación vencida", insight.titulo)

    def test_sin_vencidas_no_aparece(self):
        self.crear("Internet", 120000, 5)
        self.assertNotIn("vencidas", self.claves())

    def test_una_pagada_no_cuenta_como_vencida(self):
        self.crear("Agua", 74500, -10, pagada=True, fecha_pago=HOY)
        self.assertNotIn("vencidas", self.claves())


class ReglaProximosDiasTests(BaseInsights):
    """El ejemplo literal de §19."""

    def test_cuenta_las_de_los_proximos_siete_dias(self):
        self.crear("A", 100000, 1)
        self.crear("B", 100000, 3)
        self.crear("C", 100000, 6)
        self.crear("D", 100000, 7)
        self.crear("Lejana", 100000, 40)

        insight = self.por_clave("proximos_7_dias")
        self.assertIn("4 obligaciones", insight.titulo)
        self.assertIn("próximos 7 días", insight.titulo)
        self.assertIn("$400.000", insight.detalle)

    def test_el_dia_ocho_queda_fuera(self):
        self.crear("Justo fuera", 100000, 8)
        self.assertNotIn("proximos_7_dias", self.claves())

    def test_las_vencidas_no_se_cuentan_aqui(self):
        self.crear("Vencida", 100000, -3)
        self.assertNotIn("proximos_7_dias", self.claves())


class ReglaCategoriaTests(BaseInsights):

    def test_detecta_la_categoria_con_mas_obligaciones(self):
        for i in range(4):
            self.crear(f"Servicio {i}", 50000, 10 + i, categoria=self.servicios)
        self.crear("Crédito", 500000, 5, categoria=self.creditos)

        insight = self.por_clave("categoria_dominante")
        self.assertIn("Servicios", insight.titulo)
        self.assertIn("4 de 5", insight.detalle)
        self.assertIn("80%", insight.detalle)

    def test_detecta_donde_se_concentra_el_dinero(self):
        self.crear("Arriendo", 700000, 10, categoria=self.vivienda)
        self.crear("Administración", 200000, 11, categoria=self.vivienda)
        self.crear("Internet", 100000, 12, categoria=self.servicios)
        self.crear("Agua", 50000, 13, categoria=self.servicios)

        insight = self.por_clave("categoria_mas_cara")
        self.assertIn("Vivienda", insight.titulo)
        self.assertIn("86%", insight.titulo)

    def test_no_repite_lo_que_ya_dijo_la_obligacion_mas_alta(self):
        """Si la categoría pesa por una sola obligación, sobra el insight."""
        self.crear("Arriendo", 900000, 10, categoria=self.vivienda)
        self.crear("Internet", 100000, 11, categoria=self.servicios)
        self.crear("Agua", 50000, 12, categoria=self.servicios)

        claves = self.claves()
        self.assertIn("obligacion_mas_alta", claves)
        self.assertNotIn("categoria_mas_cara", claves)

    def test_si_esta_repartido_no_dice_nada(self):
        """Con el reparto natural entre tres categorías no hay observación."""
        self.crear("A", 100000, 10, categoria=self.vivienda)
        self.crear("B", 100000, 11, categoria=self.servicios)
        self.crear("C", 100000, 12, categoria=self.creditos)

        self.assertNotIn("categoria_mas_cara", self.claves())

    def test_el_umbral_esta_en_el_45_por_ciento(self):
        # Créditos = 400.000 de 1.000.000 = 40% -> no llega
        self.crear("A", 400000, 10, categoria=self.creditos)
        self.crear("B", 300000, 11, categoria=self.servicios)
        self.crear("C", 300000, 12, categoria=self.vivienda)
        self.assertNotIn("categoria_mas_cara", self.claves())

        # Al subir a 600.000 de 1.200.000 = 50% -> sí lo dice
        self.crear("D", 200000, 13, categoria=self.creditos)
        self.assertIn("categoria_mas_cara", self.claves())


class ReglaConcentracionFechasTests(BaseInsights):
    """El ejemplo de §19 sobre los días 25 al 30."""

    def test_detecta_la_concentracion_a_fin_de_mes(self):
        for dia in (25, 26, 28, 30):
            Obligacion.objects.create(
                usuario=self.usuario, concepto=f"O-{dia}", monto=Decimal("100000"),
                fecha_vencimiento=date(2026, 9, dia), categoria=self.servicios,
            )

        insight = self.por_clave("concentracion_fechas")
        self.assertIn("entre los días 21 y 31", insight.titulo)
        self.assertIn("100%", insight.detalle)

    def test_si_estan_repartidas_no_dice_nada(self):
        """Dos de cuatro en un tramo es casualidad, no un patrón."""
        for dia in (3, 12, 22, 27):
            Obligacion.objects.create(
                usuario=self.usuario, concepto=f"O-{dia}", monto=Decimal("100000"),
                fecha_vencimiento=date(2026, 9, dia), categoria=self.servicios,
            )

        self.assertNotIn("concentracion_fechas", self.claves())


class ReglaPuntualidadTests(BaseInsights):

    def test_reconoce_al_que_paga_a_tiempo(self):
        for i in range(3):
            self.crear(f"Pagada {i}", 100000, -10 - i, pagada=True,
                       fecha_pago=HOY - timedelta(days=20))

        insight = self.por_clave("puntualidad")
        self.assertIn("a tiempo todas", insight.titulo)
        self.assertEqual(insight.tono, "positivo")

    def test_avisa_al_que_paga_tarde(self):
        for i in range(3):
            self.crear(f"Tardía {i}", 100000, -20 - i, pagada=True, fecha_pago=HOY)

        insight = self.por_clave("puntualidad")
        self.assertIn("después del vencimiento", insight.titulo)
        self.assertEqual(insight.tono, "atencion")
        self.assertIn("recordatorios", insight.detalle)

    def test_con_menos_de_tres_pagos_no_opina(self):
        self.crear("Una", 100000, -10, pagada=True, fecha_pago=HOY)
        self.assertNotIn("puntualidad", self.claves())


class ReglaSinRecordatoriosTests(BaseInsights):

    def test_detecta_las_que_no_tienen_avisos(self):
        self.crear("Sin avisos", 100000, 10)

        insight = self.por_clave("sin_recordatorios")
        self.assertIsNotNone(insight)
        self.assertIn("1 de tus obligaciones", insight.titulo)

    def test_si_todas_tienen_avisos_no_aparece(self):
        obligacion = self.crear("Con avisos", 100000, 10)
        aplicar_reglas(obligacion, [7, 1])

        self.assertNotIn("sin_recordatorios", self.claves())


class ReglaObligacionMasAltaTests(BaseInsights):

    def test_detecta_la_que_mas_pesa(self):
        self.crear("Arriendo", 900000, 10)
        self.crear("Internet", 100000, 11)
        self.crear("Agua", 50000, 12)

        insight = self.por_clave("obligacion_mas_alta")
        self.assertIn("Arriendo", insight.titulo)
        self.assertIn("86%", insight.titulo)

    def test_si_ninguna_destaca_no_dice_nada(self):
        for i in range(4):
            self.crear(f"O-{i}", 100000, 10 + i)

        self.assertNotIn("obligacion_mas_alta", self.claves())


class AislamientoTests(BaseInsights):

    def test_no_mira_los_datos_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        Obligacion.objects.create(
            usuario=otro, concepto="Ajena", monto=Decimal("9000000"),
            fecha_vencimiento=HOY - timedelta(days=5), categoria=self.servicios,
        )

        self.assertEqual(insights.generar(self.usuario, HOY), [])


class VistaInsightsTests(BaseInsights):

    def test_responde_200(self):
        respuesta = self.client.get(reverse("analitica:insights"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "analitica/insights.html")

    def test_exige_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse("analitica:insights"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/entrar/", respuesta.url)

    def test_declara_que_no_usa_inteligencia_artificial(self):
        """§19: si el análisis es por reglas, la interfaz debe decirlo."""
        respuesta = self.client.get(reverse("analitica:insights"))
        self.assertContains(respuesta, "No intervienen modelos de inteligencia artificial")

    def test_cada_insight_declara_su_fuente(self):
        self.crear("Energía", 185000, -4)
        respuesta = self.client.get(reverse("analitica:insights"))

        for insight in respuesta.context["insights"]:
            with self.subTest(clave=insight.clave):
                self.assertTrue(insight.fuente)

    def test_sin_datos_muestra_el_mensaje_vacio(self):
        respuesta = self.client.get(reverse("analitica:insights"))
        self.assertContains(respuesta, "Todavía no hay observaciones")


class ExtensibilidadTests(BaseInsights):
    """§39: añadir o sustituir una regla no debe tocar el módulo."""

    def test_todas_las_reglas_aceptan_el_mismo_contrato(self):
        self.crear("Internet", 120000, 3)
        datos = insights.construir_datos(self.usuario, HOY)

        for regla in insights.REGLAS:
            with self.subTest(regla=regla.__name__):
                resultado = regla(datos)
                self.assertTrue(
                    resultado is None or isinstance(resultado, insights.Insight)
                )

    def test_el_limite_se_respeta(self):
        self.crear("Energía", 185000, -4)
        self.crear("Internet", 120000, 3)
        self.crear("Arriendo", 900000, 6)

        self.assertLessEqual(len(insights.generar(self.usuario, HOY, limite=2)), 2)
