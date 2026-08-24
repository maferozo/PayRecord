from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import timezone

from apps.core.templatetags.formato import (
    dias_restantes,
    moneda_cop,
    texto_vencimiento,
)


class MonedaCopTests(SimpleTestCase):
    """Formato de pesos colombianos: $1.250.000 (§22)."""

    def test_formatea_valor_entero(self):
        self.assertEqual(moneda_cop(1250000), "$1.250.000")

    def test_formatea_decimal_redondeando_a_peso(self):
        self.assertEqual(moneda_cop(Decimal("120000.49")), "$120.000")
        self.assertEqual(moneda_cop(Decimal("35900.50")), "$35.900")

    def test_valor_pequeno_sin_separador(self):
        self.assertEqual(moneda_cop(500), "$500")

    def test_valor_negativo(self):
        self.assertEqual(moneda_cop(Decimal("-45000")), "-$45.000")

    def test_valores_no_validos_devuelven_cero(self):
        self.assertEqual(moneda_cop(None), "$0")
        self.assertEqual(moneda_cop(""), "$0")
        self.assertEqual(moneda_cop("abc"), "$0")


class DiasRestantesTests(SimpleTestCase):

    def test_fecha_futura(self):
        self.assertEqual(dias_restantes(timezone.localdate() + timedelta(days=5)), 5)

    def test_fecha_pasada_es_negativa(self):
        self.assertEqual(dias_restantes(timezone.localdate() - timedelta(days=3)), -3)

    def test_hoy_es_cero(self):
        self.assertEqual(dias_restantes(timezone.localdate()), 0)

    def test_valor_no_fecha(self):
        self.assertIsNone(dias_restantes("2026-08-25"))


class TextoVencimientoTests(SimpleTestCase):

    def test_frases(self):
        hoy = timezone.localdate()
        casos = [
            (hoy, "Vence hoy"),
            (hoy + timedelta(days=1), "Vence mañana"),
            (hoy + timedelta(days=3), "Vence en 3 días"),
            (hoy - timedelta(days=1), "Vencida ayer"),
            (hoy - timedelta(days=4), "Vencida hace 4 días"),
        ]
        for fecha, esperado in casos:
            with self.subTest(fecha=fecha):
                self.assertEqual(texto_vencimiento(fecha), esperado)
