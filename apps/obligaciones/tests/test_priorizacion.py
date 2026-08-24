from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.obligaciones.enums import Prioridad
from apps.obligaciones.services.priorizacion import (
    ContextoPriorizacion,
    calcular_prioridad,
    construir_contexto,
    priorizar,
)

HOY = date(2026, 8, 24)


def obligacion_falsa(dias, monto, prioridad=Prioridad.MEDIA, peso_categoria=0,
                     pagada=False, nombre_categoria="Servicios"):
    """El algoritmo es una función pura: no necesita el modelo real."""
    return SimpleNamespace(
        fecha_vencimiento=HOY + timedelta(days=dias),
        monto=Decimal(monto),
        prioridad_usuario=prioridad,
        pagada=pagada,
        categoria=SimpleNamespace(peso_prioridad=peso_categoria, nombre=nombre_categoria),
    )


class ComponenteUrgenciaTests(SimpleTestCase):
    """La urgencia domina el puntaje (§12)."""

    def setUp(self):
        self.contexto = ContextoPriorizacion(hoy=HOY, promedio_pendiente=Decimal("100000"))

    def test_a_menor_plazo_mayor_puntaje(self):
        plazos = [-10, -2, 0, 1, 3, 7, 15, 30, 60]
        puntajes = [
            calcular_prioridad(obligacion_falsa(d, 100000), self.contexto).puntaje
            for d in plazos
        ]
        self.assertEqual(puntajes, sorted(puntajes, reverse=True))

    def test_una_vencida_siempre_supera_a_una_futura_equivalente(self):
        vencida = calcular_prioridad(obligacion_falsa(-3, 100000), self.contexto)
        futura = calcular_prioridad(obligacion_falsa(20, 100000), self.contexto)
        self.assertGreater(vencida.puntaje, futura.puntaje)

    def test_el_motivo_explica_el_vencimiento(self):
        casos = {
            0: "Vence hoy",
            1: "Vence mañana",
            -1: "Vencida hace 1 día",
            -5: "Vencida hace 5 días",
            -20: "Vencida hace más de una semana",
        }
        for dias, esperado in casos.items():
            with self.subTest(dias=dias):
                resultado = calcular_prioridad(obligacion_falsa(dias, 100000), self.contexto)
                self.assertIn(esperado, resultado.motivos)


class ComponenteMontoTests(SimpleTestCase):
    """El monto pesa en relación con lo que ese usuario suele deber."""

    def test_el_mismo_monto_pesa_distinto_segun_el_usuario(self):
        obligacion = obligacion_falsa(10, 500000)

        modesto = ContextoPriorizacion(hoy=HOY, promedio_pendiente=Decimal("100000"))
        holgado = ContextoPriorizacion(hoy=HOY, promedio_pendiente=Decimal("5000000"))

        self.assertGreater(
            calcular_prioridad(obligacion, modesto).puntaje,
            calcular_prioridad(obligacion, holgado).puntaje,
        )

    def test_un_monto_muy_alto_se_explica(self):
        contexto = ContextoPriorizacion(hoy=HOY, promedio_pendiente=Decimal("100000"))
        resultado = calcular_prioridad(obligacion_falsa(10, 400000), contexto)
        self.assertIn("Monto muy alto frente a tus obligaciones pendientes", resultado.motivos)

    def test_sin_promedio_no_revienta(self):
        contexto = ContextoPriorizacion(hoy=HOY, promedio_pendiente=Decimal("0"))
        resultado = calcular_prioridad(obligacion_falsa(5, 100000), contexto)
        self.assertGreater(resultado.puntaje, 0)


class ComponentesUsuarioYCategoriaTests(SimpleTestCase):

    def setUp(self):
        self.contexto = ContextoPriorizacion(hoy=HOY, promedio_pendiente=Decimal("100000"))

    def test_la_preferencia_del_usuario_suma(self):
        alta = calcular_prioridad(obligacion_falsa(20, 100000, Prioridad.ALTA), self.contexto)
        baja = calcular_prioridad(obligacion_falsa(20, 100000, Prioridad.BAJA), self.contexto)
        self.assertEqual(alta.puntaje - baja.puntaje, 15)
        self.assertIn("La marcaste como prioridad alta", alta.motivos)

    def test_la_preferencia_no_anula_la_urgencia(self):
        """Algo lejano marcado como alta no debe superar a algo vencido."""
        lejana_alta = calcular_prioridad(
            obligacion_falsa(60, 100000, Prioridad.ALTA, peso_categoria=5), self.contexto
        )
        vencida_baja = calcular_prioridad(
            obligacion_falsa(-3, 100000, Prioridad.BAJA), self.contexto
        )
        self.assertGreater(vencida_baja.puntaje, lejana_alta.puntaje)

    def test_la_categoria_critica_suma_y_se_explica(self):
        resultado = calcular_prioridad(
            obligacion_falsa(20, 100000, peso_categoria=5, nombre_categoria="Créditos"),
            self.contexto,
        )
        self.assertIn("«Créditos» es una categoría crítica", resultado.motivos)

    def test_el_peso_de_categoria_se_limita_a_cinco(self):
        """Un dato corrupto en la base no debe desbordar el puntaje."""
        normal = calcular_prioridad(obligacion_falsa(20, 100000, peso_categoria=5), self.contexto)
        excesivo = calcular_prioridad(obligacion_falsa(20, 100000, peso_categoria=99), self.contexto)
        self.assertEqual(normal.puntaje, excesivo.puntaje)


class BandasYLimitesTests(SimpleTestCase):

    def setUp(self):
        self.contexto = ContextoPriorizacion(hoy=HOY, promedio_pendiente=Decimal("100000"))

    def test_el_puntaje_nunca_pasa_de_cien(self):
        peor_caso = obligacion_falsa(-30, 10000000, Prioridad.ALTA, peso_categoria=5)
        self.assertLessEqual(calcular_prioridad(peor_caso, self.contexto).puntaje, 100)

    def test_el_puntaje_nunca_baja_de_cero(self):
        mejor_caso = obligacion_falsa(365, 1, Prioridad.BAJA, peso_categoria=0)
        self.assertGreaterEqual(calcular_prioridad(mejor_caso, self.contexto).puntaje, 0)

    def test_una_pagada_no_compite(self):
        resultado = calcular_prioridad(
            obligacion_falsa(-30, 5000000, Prioridad.ALTA, pagada=True), self.contexto
        )
        self.assertEqual(resultado.puntaje, 0)
        self.assertEqual(resultado.motivos, ["Ya está pagada"])

    def test_las_bandas_tienen_indicador_de_color(self):
        indicadores = {"ALTA": "🔴", "MEDIA": "🟡", "BAJA": "🟢"}
        for dias, banda in [(-5, "ALTA"), (3, "MEDIA"), (90, "BAJA")]:
            with self.subTest(dias=dias):
                resultado = calcular_prioridad(obligacion_falsa(dias, 100000), self.contexto)
                self.assertEqual(resultado.banda, banda)
                self.assertEqual(resultado.indicador, indicadores[banda])

    def test_siempre_hay_al_menos_un_motivo(self):
        for dias in (-10, 0, 5, 100):
            with self.subTest(dias=dias):
                resultado = calcular_prioridad(obligacion_falsa(dias, 100000), self.contexto)
                self.assertTrue(resultado.motivos)


class EjemploDeLaEspecificacionTests(SimpleTestCase):
    """Reproduce literalmente el ejemplo de §11.

        🔴 Crédito   $450.000  Vence mañana
        🟡 Internet  $120.000  Vence en 3 días
        🟢 Netflix   $35.900   Vence en 10 días
    """

    def test_el_ejemplo_se_reproduce(self):
        credito = obligacion_falsa(1, 450000, Prioridad.ALTA, peso_categoria=5,
                                   nombre_categoria="Créditos")
        internet = obligacion_falsa(3, 120000, Prioridad.MEDIA, peso_categoria=3)
        netflix = obligacion_falsa(10, 35900, Prioridad.BAJA, peso_categoria=1,
                                   nombre_categoria="Suscripciones")

        # El promedio corresponde a las obligaciones pendientes de María
        # en los datos de prueba de §37.
        contexto = construir_contexto([credito, internet, netflix], HOY)

        resultados = {
            "credito": calcular_prioridad(credito, contexto),
            "internet": calcular_prioridad(internet, contexto),
            "netflix": calcular_prioridad(netflix, contexto),
        }

        self.assertEqual(resultados["credito"].banda, "ALTA")
        self.assertEqual(resultados["internet"].banda, "MEDIA")
        self.assertEqual(resultados["netflix"].banda, "BAJA")

    def test_el_orden_es_el_esperado(self):
        credito = obligacion_falsa(1, 450000, Prioridad.ALTA, peso_categoria=5)
        internet = obligacion_falsa(3, 120000, Prioridad.MEDIA, peso_categoria=3)
        netflix = obligacion_falsa(10, 35900, Prioridad.BAJA, peso_categoria=1)

        contexto = construir_contexto([credito, internet, netflix], HOY)
        ordenadas = priorizar([netflix, internet, credito], contexto)

        self.assertEqual([par[0] for par in ordenadas], [credito, internet, netflix])


class DeterminismoTests(SimpleTestCase):

    def test_dos_ejecuciones_dan_el_mismo_resultado(self):
        contexto = ContextoPriorizacion(hoy=HOY, promedio_pendiente=Decimal("300000"))
        obligacion = obligacion_falsa(4, 250000, Prioridad.ALTA, peso_categoria=4)

        primero = calcular_prioridad(obligacion, contexto)
        segundo = calcular_prioridad(obligacion, contexto)

        self.assertEqual(primero.puntaje, segundo.puntaje)
        self.assertEqual(primero.motivos, segundo.motivos)
