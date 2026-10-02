"""Pruebas del asistente PayRecord AI.

No hacen ninguna llamada real a la API de Gemini: `preguntar()` y
`generar_resumen()` se simulan con `unittest.mock`. Lo que sí se prueba de
verdad es lo que no depende de la red: que las herramientas que Gemini
puede llamar devuelven datos reales (nunca inventados) y aíslan por usuario,
y que el endpoint valida igual que el resto de PAYRECORD.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.analitica.services import asistente_ia
from apps.obligaciones.models import Categoria, Obligacion

Usuario = get_user_model()

HOY = date(2026, 8, 24)


class BaseAsistente(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.servicios = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)

    def crear(self, monto, dias, concepto="Internet", categoria=None):
        from datetime import timedelta

        return Obligacion.objects.create(
            usuario=self.usuario,
            concepto=concepto,
            monto=Decimal(monto),
            fecha_vencimiento=HOY + timedelta(days=dias),
            categoria=categoria or self.servicios,
        )


class DisponibleTests(TestCase):

    @override_settings(GEMINI_API_KEY="")
    def test_sin_clave_no_esta_disponible(self):
        self.assertFalse(asistente_ia.disponible())

    @override_settings(GEMINI_API_KEY="una-clave-de-prueba")
    def test_con_clave_esta_disponible(self):
        self.assertTrue(asistente_ia.disponible())


class ToolsLecturaTests(BaseAsistente):
    """Las herramientas que Gemini puede llamar: solo datos reales, aisladas
    por usuario — nunca un bloque de contexto precalculado."""

    def _tools(self, usuario=None, hoy=HOY):
        herramientas = asistente_ia._tools_lectura(usuario or self.usuario, hoy)
        return {fn.__name__: fn for fn in herramientas}

    def test_resumen_financiero_usa_montos_reales(self):
        self.crear(120000, 3)
        self.crear(50000, -5, concepto="Vencida")

        resultado = self._tools()["obtener_resumen_financiero"]()

        self.assertEqual(resultado["total_pendiente"], 170000.0)
        self.assertEqual(resultado["obligaciones_pendientes"], 2)
        self.assertEqual(resultado["obligaciones_vencidas"], 1)

    def test_consultar_por_periodo_filtra_por_fechas(self):
        self.crear(100000, 3, concepto="Dentro del rango")
        self.crear(999999, 40, concepto="Fuera del rango")

        resultado = self._tools()["consultar_obligaciones_por_periodo"](
            fecha_inicio=HOY.isoformat(), fecha_fin=(HOY + timedelta(days=10)).isoformat(),
        )

        self.assertEqual(resultado["cantidad"], 1)
        self.assertEqual(resultado["obligaciones"][0]["titulo"], "Dentro del rango")

    def test_consultar_por_periodo_fecha_invalida_no_revienta(self):
        resultado = self._tools()["consultar_obligaciones_por_periodo"](
            fecha_inicio="no-es-una-fecha", fecha_fin=HOY.isoformat(),
        )
        self.assertIn("error", resultado)

    def test_mayor_obligacion_devuelve_titulo_no_categoria(self):
        self.crear(900000, 5, concepto="Universidad", categoria=self.servicios)
        self.crear(100000, 3, concepto="Internet")

        resultado = self._tools()["obtener_mayor_obligacion"]()

        self.assertTrue(resultado["existe"])
        self.assertEqual(resultado["titulo"], "Universidad")
        self.assertEqual(resultado["categoria"], self.servicios.nombre)
        self.assertNotEqual(resultado["titulo"], resultado["categoria"])

    def test_sin_obligaciones_mayor_obligacion_lo_dice_claro(self):
        resultado = self._tools()["obtener_mayor_obligacion"]()
        self.assertFalse(resultado["existe"])

    def test_dinero_por_categoria_usa_datos_reales(self):
        self.crear(100000, 3, categoria=self.servicios)
        resultado = self._tools()["consultar_dinero_por_categoria"]()
        total = sum(c["total"] for c in resultado["categorias"])
        self.assertEqual(total, 100000.0)

    def test_no_mezcla_datos_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        Obligacion.objects.create(
            usuario=otro, concepto="Secreto de otro", monto=Decimal("9999999"),
            fecha_vencimiento=HOY, categoria=self.servicios,
        )
        self.crear(100000, 3)

        resultado = self._tools()["obtener_resumen_financiero"]()
        self.assertEqual(resultado["total_pendiente"], 100000.0)

        periodo = self._tools()["consultar_obligaciones_por_periodo"](
            fecha_inicio=(HOY - timedelta(days=5)).isoformat(),
            fecha_fin=(HOY + timedelta(days=5)).isoformat(),
        )
        titulos = [o["titulo"] for o in periodo["obligaciones"]]
        self.assertNotIn("Secreto de otro", titulos)


class VistaAsistenteTests(BaseAsistente):

    def url(self):
        return reverse("analitica:asistente_preguntar")

    @override_settings(GEMINI_API_KEY="")
    def test_sin_clave_configurada_devuelve_503(self):
        respuesta = self.client.post(self.url(), {"pregunta": "¿Cuánto tengo pendiente?"})
        self.assertEqual(respuesta.status_code, 503)

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    def test_pregunta_vacia_devuelve_400(self):
        respuesta = self.client.post(self.url(), {"pregunta": "  "})
        self.assertEqual(respuesta.status_code, 400)

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    def test_pregunta_demasiado_larga_devuelve_400(self):
        respuesta = self.client.post(self.url(), {"pregunta": "x" * 501})
        self.assertEqual(respuesta.status_code, 400)

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    @patch("apps.analitica.services.asistente_ia.preguntar")
    def test_pregunta_valida_devuelve_la_respuesta(self, preguntar_simulado):
        preguntar_simulado.return_value = "Tienes $120.000 pendientes."

        respuesta = self.client.post(self.url(), {"pregunta": "¿Cuánto tengo pendiente?"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["respuesta"], "Tienes $120.000 pendientes.")
        preguntar_simulado.assert_called_once()
        # La pregunta que llega al servicio es la del usuario, no otra cosa.
        self.assertEqual(preguntar_simulado.call_args.args[1], "¿Cuánto tengo pendiente?")

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    @patch("apps.analitica.services.asistente_ia.generar_resumen")
    def test_boton_de_resumen_no_necesita_pregunta(self, resumen_simulado):
        resumen_simulado.return_value = "Resumen: todo al día."

        respuesta = self.client.post(self.url(), {"resumen": "1"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["respuesta"], "Resumen: todo al día.")

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    @patch("apps.analitica.services.asistente_ia.preguntar")
    def test_error_del_asistente_se_traduce_a_502(self, preguntar_simulado):
        preguntar_simulado.side_effect = asistente_ia.AsistenteError("La clave no es válida.")

        respuesta = self.client.post(self.url(), {"pregunta": "¿Cuánto debo?"})

        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(respuesta.json()["error"], "La clave no es válida.")

    def test_exige_sesion(self):
        self.client.logout()
        respuesta = self.client.post(self.url(), {"pregunta": "¿Cuánto debo?"})
        self.assertNotEqual(respuesta.status_code, 200)

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    def test_solo_acepta_post(self):
        respuesta = self.client.get(self.url())
        self.assertEqual(respuesta.status_code, 405)
