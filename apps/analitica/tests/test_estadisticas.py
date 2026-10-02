import json
import re
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.analitica import selectors
from apps.obligaciones.models import Categoria, Obligacion

Usuario = get_user_model()

HOY = date(2026, 8, 24)


class BaseAnalitica(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.servicios = Categoria.objects.get(codigo="servicios")
        cls.creditos = Categoria.objects.get(codigo="creditos")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)

    def crear(self, monto, dias, pagada=False, categoria=None, usuario=None,
              fecha_pago=None):
        vencimiento = HOY + timedelta(days=dias)
        return Obligacion.objects.create(
            usuario=usuario or self.usuario,
            concepto=f"O-{monto}-{dias}",
            monto=Decimal(monto),
            fecha_vencimiento=vencimiento,
            categoria=categoria or self.servicios,
            pagada=pagada,
            fecha_pago=fecha_pago if pagada else None,
        )


class TotalesTests(BaseAnalitica):
    """§18: total de obligaciones, pagado, pendiente y vencido."""

    def test_calcula_las_cuatro_cifras(self):
        self.crear(100000, -5)                     # vencida
        self.crear(200000, 3)                      # próxima
        self.crear(300000, 60)                     # pendiente
        self.crear(50000, -10, pagada=True, fecha_pago=HOY - timedelta(days=11))

        datos = selectors.totales(self.usuario, HOY)

        self.assertEqual(datos["cantidad"], 4)
        self.assertEqual(datos["valor_total"], Decimal("650000"))
        self.assertEqual(datos["pagado"], Decimal("50000"))
        self.assertEqual(datos["pendiente"], Decimal("600000"))
        self.assertEqual(datos["vencido"], Decimal("100000"))

    def test_porcentaje_pagado(self):
        self.crear(100000, 5)
        self.crear(100000, 5, pagada=True, fecha_pago=HOY)
        self.crear(100000, 5, pagada=True, fecha_pago=HOY)
        self.crear(100000, 5)

        datos = selectors.totales(self.usuario, HOY)
        self.assertEqual(datos["porcentaje_pagado"], 50)

    def test_sin_obligaciones_no_divide_por_cero(self):
        datos = selectors.totales(self.usuario, HOY)
        self.assertEqual(datos["cantidad"], 0)
        self.assertEqual(datos["valor_total"], Decimal("0"))
        self.assertEqual(datos["porcentaje_pagado"], 0)

    def test_no_suma_obligaciones_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear(9000000, 5, usuario=otro)
        self.crear(100000, 5)

        datos = selectors.totales(self.usuario, HOY)
        self.assertEqual(datos["valor_total"], Decimal("100000"))

    def test_no_suma_las_eliminadas(self):
        obligacion = self.crear(500000, 5)
        obligacion.eliminar_logicamente()
        self.crear(100000, 5)

        datos = selectors.totales(self.usuario, HOY)
        self.assertEqual(datos["valor_total"], Decimal("100000"))


class PorEstadoTests(BaseAnalitica):

    def test_devuelve_siempre_los_cuatro_estados(self):
        """Aunque estén vacíos, para que el gráfico no cambie de forma."""
        filas = selectors.por_estado(self.usuario, HOY)

        self.assertEqual(len(filas), 4)
        self.assertTrue(all(fila["cantidad"] == 0 for fila in filas))

    def test_cuenta_y_suma_cada_estado(self):
        self.crear(100000, -5)
        self.crear(200000, 3)
        self.crear(300000, 60)

        filas = {fila["estado"]: fila for fila in selectors.por_estado(self.usuario, HOY)}

        self.assertEqual(filas["VENCIDA"]["total"], Decimal("100000"))
        self.assertEqual(filas["PROXIMA_VENCER"]["total"], Decimal("200000"))
        self.assertEqual(filas["PENDIENTE"]["total"], Decimal("300000"))
        self.assertEqual(filas["PAGADA"]["cantidad"], 0)


class PorCategoriaTests(BaseAnalitica):

    def test_agrupa_y_ordena_por_valor(self):
        self.crear(100000, 5, categoria=self.servicios)
        self.crear(50000, 6, categoria=self.servicios)
        self.crear(900000, 7, categoria=self.creditos)

        filas = selectors.por_categoria(self.usuario, HOY)

        self.assertEqual(filas[0]["categoria__nombre"], "Créditos")
        self.assertEqual(filas[0]["total"], Decimal("900000"))
        self.assertEqual(filas[1]["cantidad"], 2)
        self.assertEqual(filas[1]["total"], Decimal("150000"))

    def test_incluye_las_pagadas(self):
        """§18 pide el reparto de todas las obligaciones, no solo las vivas."""
        self.crear(100000, -5, pagada=True, fecha_pago=HOY, categoria=self.creditos)

        filas = selectors.por_categoria(self.usuario, HOY)
        self.assertEqual(filas[0]["total"], Decimal("100000"))


class EvolucionMensualTests(BaseAnalitica):

    def test_devuelve_el_numero_de_meses_pedido(self):
        serie = selectors.evolucion_mensual(self.usuario, meses=6, hoy=HOY)
        self.assertEqual(len(serie), 6)

    def test_el_ultimo_mes_es_el_actual(self):
        serie = selectors.evolucion_mensual(self.usuario, meses=6, hoy=HOY)
        self.assertEqual(serie[-1]["etiqueta"], "ago 26")
        self.assertEqual(serie[0]["etiqueta"], "mar 26")

    def test_rellena_los_meses_sin_datos(self):
        """Un hueco en el gráfico se leería como un mes inexistente."""
        self.crear(100000, 0)
        serie = selectors.evolucion_mensual(self.usuario, meses=6, hoy=HOY)

        self.assertTrue(all("pagado" in fila and "sin_pagar" in fila for fila in serie))
        self.assertEqual(serie[0]["pagado"], Decimal("0"))

    def test_separa_pagado_de_no_pagado(self):
        self.crear(100000, 0, pagada=True, fecha_pago=HOY)
        self.crear(300000, 1)

        serie = selectors.evolucion_mensual(self.usuario, meses=6, hoy=HOY)
        agosto = serie[-1]

        self.assertEqual(agosto["pagado"], Decimal("100000"))
        self.assertEqual(agosto["sin_pagar"], Decimal("300000"))

    def test_cruza_el_cambio_de_ano(self):
        serie = selectors.evolucion_mensual(self.usuario, meses=6, hoy=date(2027, 2, 15))
        self.assertEqual(serie[0]["etiqueta"], "sep 26")
        self.assertEqual(serie[-1]["etiqueta"], "feb 27")


class ComprometidoEsteMesTests(BaseAnalitica):
    """Estadística 1: la tarjeta principal, con variación respecto al mes anterior."""

    def test_suma_lo_que_vence_este_mes(self):
        self.crear(100000, 0)   # este mes
        self.crear(200000, 3)   # este mes
        self.crear(300000, 40)  # el mes siguiente, no cuenta aquí

        datos = selectors.comprometido_este_mes(self.usuario, hoy=HOY)
        self.assertEqual(datos["actual"], Decimal("300000"))

    def test_sin_datos_del_mes_anterior_no_inventa_porcentaje(self):
        self.crear(100000, 0)
        datos = selectors.comprometido_este_mes(self.usuario, hoy=HOY)
        self.assertIsNone(datos["porcentaje"])

    def test_calcula_el_aumento_real(self):
        self.crear(100000, -35)  # mes anterior: 100.000
        self.crear(200000, 0)    # este mes: 200.000

        datos = selectors.comprometido_este_mes(self.usuario, hoy=HOY)
        self.assertEqual(datos["anterior"], Decimal("100000"))
        self.assertEqual(datos["actual"], Decimal("200000"))
        self.assertEqual(datos["porcentaje"], 100.0)
        self.assertTrue(datos["aumento"])

    def test_calcula_la_disminucion_real(self):
        self.crear(200000, -35)  # mes anterior: 200.000
        self.crear(100000, 0)    # este mes: 100.000

        datos = selectors.comprometido_este_mes(self.usuario, hoy=HOY)
        self.assertEqual(datos["porcentaje"], -50.0)
        self.assertFalse(datos["aumento"])

    def test_incluye_pagadas_y_sin_pagar_por_igual(self):
        """"Comprometido" aquí es lo que vence, no solo lo pendiente."""
        self.crear(100000, 0, pagada=True, fecha_pago=HOY)
        self.crear(50000, 1)

        datos = selectors.comprometido_este_mes(self.usuario, hoy=HOY)
        self.assertEqual(datos["actual"], Decimal("150000"))


class GastoPorQuincenaTests(BaseAnalitica):
    """Estadística 3: primera quincena (1-15) frente a segunda (16-fin de mes)."""

    def crear_en_dia(self, monto, dia, pagada=False):
        return Obligacion.objects.create(
            usuario=self.usuario,
            concepto=f"Día {dia}",
            monto=Decimal(monto),
            fecha_vencimiento=HOY.replace(day=dia),
            categoria=self.servicios,
            pagada=pagada,
            fecha_pago=HOY if pagada else None,
        )

    def test_reparte_correctamente_segun_el_dia(self):
        self.crear_en_dia(100000, 5)   # primera
        self.crear_en_dia(200000, 15)  # primera (el corte incluye el 15)
        self.crear_en_dia(300000, 16)  # segunda
        self.crear_en_dia(400000, 28)  # segunda

        datos = selectors.gasto_por_quincena(self.usuario, hoy=HOY)

        self.assertEqual(datos["primera"]["total"], Decimal("300000"))
        self.assertEqual(datos["primera"]["cantidad"], 2)
        self.assertEqual(datos["segunda"]["total"], Decimal("700000"))
        self.assertEqual(datos["segunda"]["cantidad"], 2)

    def test_calcula_los_porcentajes(self):
        self.crear_en_dia(300000, 5)
        self.crear_en_dia(700000, 20)

        datos = selectors.gasto_por_quincena(self.usuario, hoy=HOY)
        self.assertEqual(datos["primera"]["porcentaje"], 30)
        self.assertEqual(datos["segunda"]["porcentaje"], 70)

    def test_incluye_pagadas_y_sin_pagar(self):
        self.crear_en_dia(100000, 5, pagada=True)
        self.crear_en_dia(50000, 10)

        datos = selectors.gasto_por_quincena(self.usuario, hoy=HOY)
        self.assertEqual(datos["primera"]["total"], Decimal("150000"))

    def test_no_mezcla_obligaciones_de_otros_meses(self):
        self.crear_en_dia(500000, 5)  # este mes
        self.crear(999999, 40)        # el mes siguiente, fuera de rango

        datos = selectors.gasto_por_quincena(self.usuario, hoy=HOY)
        self.assertEqual(datos["primera"]["total"], Decimal("500000"))
        self.assertEqual(datos["segunda"]["total"], Decimal("0"))

    def test_sin_datos_no_hay_porcentaje(self):
        datos = selectors.gasto_por_quincena(self.usuario, hoy=HOY)
        self.assertFalse(datos["hay_datos"])
        self.assertIsNone(datos["primera"]["porcentaje"])


class MayoresGastosTests(BaseAnalitica):
    """Estadística 4: ranking de este mes, de mayor a menor."""

    def test_ordena_de_mayor_a_menor(self):
        self.crear(100000, 3)
        self.crear(900000, 5)
        self.crear(500000, 7)

        datos = selectors.mayores_gastos(self.usuario, hoy=HOY)
        montos = [o.monto for o in datos["obligaciones"]]
        self.assertEqual(montos, [Decimal("900000"), Decimal("500000"), Decimal("100000")])

    def test_respeta_el_limite_pero_informa_el_total(self):
        for i in range(8):
            self.crear(100000 + i, i)

        datos = selectors.mayores_gastos(self.usuario, limite=5, hoy=HOY)
        self.assertEqual(len(datos["obligaciones"]), 5)
        self.assertEqual(datos["total"], 8)

    def test_no_mezcla_el_mes_siguiente(self):
        self.crear(999999, 40)  # el mes siguiente
        self.crear(100000, 3)   # este mes

        datos = selectors.mayores_gastos(self.usuario, hoy=HOY)
        self.assertEqual(datos["total"], 1)
        self.assertEqual(datos["obligaciones"][0].monto, Decimal("100000"))

    def test_no_mezcla_obligaciones_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear(5000000, 3, usuario=otro)
        self.crear(100000, 3)

        datos = selectors.mayores_gastos(self.usuario, hoy=HOY)
        self.assertEqual(datos["total"], 1)

    def test_sin_datos_devuelve_lista_vacia(self):
        datos = selectors.mayores_gastos(self.usuario, hoy=HOY)
        self.assertEqual(datos["obligaciones"], [])
        self.assertEqual(datos["total"], 0)


class ComprometidoPorMesTests(BaseAnalitica):
    """Cuánto vence cada mes hacia adelante, se haya pagado o no."""

    def test_devuelve_el_numero_de_meses_pedido(self):
        serie = selectors.comprometido_por_mes(self.usuario, meses_adelante=4, hoy=HOY)
        self.assertEqual(len(serie), 4)

    def test_el_primer_mes_es_el_actual(self):
        serie = selectors.comprometido_por_mes(self.usuario, meses_adelante=4, hoy=HOY)
        self.assertEqual(serie[0]["etiqueta"], "ago 26")
        self.assertTrue(serie[0]["es_mes_actual"])
        self.assertFalse(serie[1]["es_mes_actual"])

    def test_suma_pagadas_y_sin_pagar_por_igual(self):
        """A diferencia de `evolucion_mensual`, aquí no importa si ya se pagó:
        lo que interesa es cuánto vence ese mes."""
        self.crear(100000, 0, pagada=True, fecha_pago=HOY)
        self.crear(300000, 1)

        serie = selectors.comprometido_por_mes(self.usuario, meses_adelante=4, hoy=HOY)
        self.assertEqual(serie[0]["total"], Decimal("400000"))

    def test_un_mes_futuro_solo_suma_lo_de_ese_mes(self):
        self.crear(100000, 0)     # este mes
        self.crear(200000, 35)    # el mes siguiente

        serie = selectors.comprometido_por_mes(self.usuario, meses_adelante=4, hoy=HOY)
        self.assertEqual(serie[0]["total"], Decimal("100000"))
        self.assertEqual(serie[1]["total"], Decimal("200000"))

    def test_lo_ya_vencido_de_meses_anteriores_no_aparece(self):
        """Esta serie mira hacia adelante: lo vencido se ve en "por estado",
        no aquí duplicado."""
        self.crear(500000, -40)  # venció hace más de un mes

        serie = selectors.comprometido_por_mes(self.usuario, meses_adelante=4, hoy=HOY)
        self.assertEqual(sum(fila["total"] for fila in serie), Decimal("0"))


class ProximosVencimientosTests(BaseAnalitica):

    def test_ordena_por_fecha_mas_cercana(self):
        self.crear(100000, 10)
        cercana = self.crear(200000, 2)

        proximos = selectors.proximos_vencimientos(self.usuario, hoy=HOY)
        self.assertEqual(proximos[0].pk, cercana.pk)

    def test_las_pagadas_no_aparecen(self):
        self.crear(100000, 3, pagada=True, fecha_pago=HOY)
        pendiente = self.crear(200000, 5)

        proximos = selectors.proximos_vencimientos(self.usuario, hoy=HOY)
        self.assertEqual([o.pk for o in proximos], [pendiente.pk])

    def test_respeta_el_limite(self):
        for dias in range(10):
            self.crear(100000, dias)

        proximos = selectors.proximos_vencimientos(self.usuario, limite=3, hoy=HOY)
        self.assertEqual(len(proximos), 3)


class CumplimientoTests(BaseAnalitica):
    """Qué proporción de lo pagado se pagó a tiempo (§38)."""

    def test_sin_pagos_no_hay_porcentaje(self):
        datos = selectors.cumplimiento(self.usuario, HOY)
        self.assertIsNone(datos["porcentaje"])
        self.assertEqual(datos["total"], 0)

    def test_pago_anticipado_cuenta_como_a_tiempo(self):
        self.crear(100000, 5, pagada=True, fecha_pago=HOY)  # vence en 5 días
        datos = selectors.cumplimiento(self.usuario, HOY)

        self.assertEqual(datos["a_tiempo"], 1)
        self.assertEqual(datos["porcentaje"], 100)

    def test_pago_el_mismo_dia_cuenta_como_a_tiempo(self):
        self.crear(100000, 0, pagada=True, fecha_pago=HOY)
        self.assertEqual(selectors.cumplimiento(self.usuario, HOY)["a_tiempo"], 1)

    def test_pago_tardio_se_detecta(self):
        obligacion = self.crear(100000, -10, pagada=True, fecha_pago=HOY)
        self.assertGreater(obligacion.fecha_pago, obligacion.fecha_vencimiento)

        datos = selectors.cumplimiento(self.usuario, HOY)
        self.assertEqual(datos["tarde"], 1)
        self.assertEqual(datos["porcentaje"], 0)

    def test_mezcla(self):
        self.crear(100000, 5, pagada=True, fecha_pago=HOY)
        self.crear(100000, 6, pagada=True, fecha_pago=HOY)
        self.crear(100000, -10, pagada=True, fecha_pago=HOY)

        datos = selectors.cumplimiento(self.usuario, HOY)
        self.assertEqual(datos["total"], 3)
        self.assertEqual(datos["porcentaje"], 67)


class VistaEstadisticasTests(BaseAnalitica):

    def test_responde_200(self):
        respuesta = self.client.get(reverse("analitica:estadisticas"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "analitica/estadisticas.html")

    def test_exige_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse("analitica:estadisticas"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/entrar/", respuesta.url)

    def test_sin_datos_muestra_el_mensaje_vacio(self):
        respuesta = self.client.get(reverse("analitica:estadisticas"))
        self.assertFalse(respuesta.context["hay_datos"])
        self.assertContains(respuesta, "Todavía no hay datos suficientes")

    def test_con_datos_serializa_los_graficos(self):
        """Los `grafico_*` del contexto son dicts planos, no JSON ya serializado.

        `json_script` en la plantilla hace su propio `json.dumps`; pasarle
        una cadena ya serializada la codifica dos veces (el navegador recibe
        texto en vez de un objeto: los gráficos quedaban en blanco).
        """
        self.crear(100000, 3)
        self.crear(200000, -5, categoria=self.creditos)

        respuesta = self.client.get(reverse("analitica:estadisticas"))
        self.assertTrue(respuesta.context["hay_datos"])

        estado = respuesta.context["grafico_estado"]
        self.assertIsInstance(estado, dict)
        self.assertEqual(len(estado["etiquetas"]), 4)
        self.assertEqual(len(estado["colores"]), 4)

        categoria = respuesta.context["grafico_categoria"]
        self.assertIn("Créditos", categoria["etiquetas"])

        evolucion = respuesta.context["grafico_evolucion"]
        self.assertEqual(len(evolucion["etiquetas"]), 6)
        self.assertEqual(len(evolucion["pagado"]), 6)

    def test_los_datos_de_graficos_son_json_valido(self):
        """Comprueba lo que de verdad llega al navegador, no el contexto.

        `<script type="application/json">` debe contener un objeto JSON
        real. Esta prueba antes leía `respuesta.context[clave]` con
        `json.loads`, lo que solo confirmaba que el valor era una cadena
        JSON válida — y por eso no detectó que esa cadena, al pasar de
        nuevo por `json_script`, terminaba doblemente codificada en el HTML.
        """
        self.crear(123456.78, 3)
        respuesta = self.client.get(reverse("analitica:estadisticas"))
        html = respuesta.content.decode()

        ids_html = {
            "grafico_estado": "datosEstado",
            "grafico_categoria": "datosCategoria",
            "grafico_comprometido": "datosComprometido",
        }
        for clave, id_html in ids_html.items():
            with self.subTest(clave=clave):
                bloque = re.search(
                    rf'<script id="{id_html}"[^>]*>(.*?)</script>', html, re.S
                )
                self.assertIsNotNone(bloque, f"no se encontró #{id_html} en el HTML")
                datos = json.loads(bloque.group(1))
                self.assertIsInstance(
                    datos, dict, f"{id_html} llegó doblemente codificado (es {type(datos)})"
                )

    def test_no_incluye_datos_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear(9000000, 5, usuario=otro, categoria=self.creditos)

        respuesta = self.client.get(reverse("analitica:estadisticas"))
        self.assertEqual(respuesta.context["totales"]["cantidad"], 0)


class FiltroFechasHistorialTests(BaseAnalitica):
    """§17: filtrar el historial por rango de fechas."""

    def setUp(self):
        super().setUp()
        self.antigua = self.crear(100000, -60)
        self.reciente = self.crear(200000, -2)
        self.futura = self.crear(300000, 40)

    def test_filtrar_desde(self):
        desde = (HOY - timedelta(days=10)).isoformat()
        respuesta = self.client.get(reverse("obligaciones:lista"), {"desde": desde})

        conceptos = [o.concepto for o in respuesta.context["obligaciones"]]
        self.assertNotIn(self.antigua.concepto, conceptos)
        self.assertIn(self.reciente.concepto, conceptos)

    def test_filtrar_hasta(self):
        hasta = HOY.isoformat()
        respuesta = self.client.get(reverse("obligaciones:lista"), {"hasta": hasta})

        conceptos = [o.concepto for o in respuesta.context["obligaciones"]]
        self.assertIn(self.reciente.concepto, conceptos)
        self.assertNotIn(self.futura.concepto, conceptos)

    def test_filtrar_por_rango(self):
        respuesta = self.client.get(reverse("obligaciones:lista"), {
            "desde": (HOY - timedelta(days=10)).isoformat(),
            "hasta": HOY.isoformat(),
        })
        conceptos = [o.concepto for o in respuesta.context["obligaciones"]]
        self.assertEqual(conceptos, [self.reciente.concepto])

    def test_un_rango_invertido_avisa(self):
        respuesta = self.client.get(reverse("obligaciones:lista"), {
            "desde": HOY.isoformat(),
            "hasta": (HOY - timedelta(days=30)).isoformat(),
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["filtros"].errors)

    def test_una_fecha_mal_escrita_no_rompe(self):
        respuesta = self.client.get(reverse("obligaciones:lista"), {"desde": "no-es-fecha"})
        self.assertEqual(respuesta.status_code, 200)
