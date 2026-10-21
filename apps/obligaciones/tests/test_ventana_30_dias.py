"""Ventana móvil de 30 días: dashboard y "Mis obligaciones" (§ encargo
final). Cubre los 10 escenarios pedidos explícitamente.

Regla implementada (apps/obligaciones/services/estados.py):
    DIAS_VENTANA_PROXIMOS = 30
    fin_de_ventana_proximos(hoy) = hoy + 30 días, ambos extremos incluidos.

No es "el mismo día del mes siguiente": un número fijo de días evita la
ambigüedad de los meses de distinta duración y del día 29/30/31 que no
existe en todos los meses, que es justo lo que el encargo pedía evitar.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.dashboard import selectors as dashboard_selectors
from apps.obligaciones.models import Categoria, Obligacion
from apps.obligaciones.services.estados import fin_de_ventana_proximos

Usuario = get_user_model()
HOY = date(2026, 10, 21)


class BaseVentana(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)

    def crear(self, concepto, dias_desde_hoy, pagada=False, usuario=None):
        return Obligacion.objects.create(
            usuario=usuario or self.usuario,
            concepto=concepto,
            monto=Decimal("50000"),
            fecha_vencimiento=HOY + timedelta(days=dias_desde_hoy),
            categoria=self.categoria,
            pagada=pagada,
        )


class ReglaDeFechasTests(BaseVentana):
    """§1: la regla principal, aislada de cualquier vista."""

    def test_fin_de_ventana_son_30_dias_exactos(self):
        self.assertEqual(fin_de_ventana_proximos(HOY), HOY + timedelta(days=30))

    def test_la_ventana_avanza_con_el_cambio_de_mes(self):
        """31 de octubre + 30 días cae en noviembre, sin duplicar ni
        desplazar nada por la distinta duración del mes."""
        fin = fin_de_ventana_proximos(date(2026, 10, 31))
        self.assertEqual(fin, date(2026, 11, 30))

    def test_la_ventana_avanza_con_el_cambio_de_ano(self):
        fin = fin_de_ventana_proximos(date(2026, 12, 15))
        self.assertEqual(fin, date(2027, 1, 14))

    def test_meses_de_distinta_duracion_no_cambian_el_ancho_de_la_ventana(self):
        """La ventana siempre son 30 días calendario, sin importar si el
        mes de partida tiene 28, 29, 30 o 31 días."""
        for inicio in (date(2027, 2, 1), date(2028, 2, 1), date(2026, 4, 1), date(2026, 1, 1)):
            with self.subTest(inicio=inicio):
                self.assertEqual((fin_de_ventana_proximos(inicio) - inicio).days, 30)


class ZonaHorariaTests(BaseVentana):
    """§5: "usuarios con distintas zonas horarias, respetando la
    configuración real del proyecto". PAYRECORD no tiene zona horaria por
    usuario (una sola, de aplicación -- TIME_ZONE="America/Bogota" en
    config/settings/base.py): lo real que hay que respetar es que "hoy"
    siempre se calcule en esa zona, no en UTC."""

    def test_la_ventana_usa_la_fecha_local_de_bogota_no_utc(self):
        import datetime
        from unittest.mock import patch

        # 23:30 en Bogotá del 20 de octubre ya es 21 de octubre en UTC.
        instante_utc = datetime.datetime(2026, 10, 21, 4, 30, tzinfo=datetime.timezone.utc)
        with patch("django.utils.timezone.now", return_value=instante_utc):
            hoy_bogota = timezone.localdate()

        self.assertEqual(hoy_bogota, date(2026, 10, 20))
        self.assertEqual(fin_de_ventana_proximos(hoy_bogota), date(2026, 11, 19))


class DashboardProximasTests(BaseVentana):
    """§2: la sección "Próximas por fecha" del dashboard."""

    def test_incluye_lo_que_vence_hoy(self):
        self.crear("Vence hoy", 0)
        proximas = dashboard_selectors.proximas_obligaciones(self.usuario, hoy=HOY)
        self.assertEqual([o.concepto for o in proximas], ["Vence hoy"])

    def test_incluye_lo_que_vence_manana(self):
        self.crear("Vence mañana", 1)
        proximas = dashboard_selectors.proximas_obligaciones(self.usuario, hoy=HOY)
        self.assertEqual([o.concepto for o in proximas], ["Vence mañana"])

    def test_incluye_el_limite_de_30_dias(self):
        self.crear("Justo en el limite", 30)
        proximas = dashboard_selectors.proximas_obligaciones(self.usuario, hoy=HOY)
        self.assertEqual([o.concepto for o in proximas], ["Justo en el limite"])

    def test_excluye_lo_que_vence_a_31_dias(self):
        self.crear("Un dia fuera", 31)
        proximas = dashboard_selectors.proximas_obligaciones(self.usuario, hoy=HOY)
        self.assertEqual(proximas, [])

    def test_excluye_una_obligacion_lejana_a_100_dias(self):
        self.crear("Muy lejana", 100)
        proximas = dashboard_selectors.proximas_obligaciones(self.usuario, hoy=HOY)
        self.assertEqual(proximas, [])

    def test_no_incluye_pagadas(self):
        self.crear("Ya pagada", 5, pagada=True)
        proximas = dashboard_selectors.proximas_obligaciones(self.usuario, hoy=HOY)
        self.assertEqual(proximas, [])

    def test_ordenadas_por_fecha_ascendente(self):
        self.crear("En 20 dias", 20)
        self.crear("Manana", 1)
        self.crear("En 10 dias", 10)
        proximas = dashboard_selectors.proximas_obligaciones(self.usuario, hoy=HOY)
        self.assertEqual([o.concepto for o in proximas], ["Manana", "En 10 dias", "En 20 dias"])

    def test_sin_obligaciones_proximas_devuelve_lista_vacia(self):
        """El estado vacío útil lo decide la plantilla ("Nada por
        vencer."); aquí se prueba que el selector no falla y da []."""
        self.assertEqual(dashboard_selectors.proximas_obligaciones(self.usuario, hoy=HOY), [])

    def test_el_resumen_del_dashboard_no_usa_la_ventana(self):
        """§6: los totales ("Dinero comprometido", tarjetas KPI) no se
        reducen a 30 días -- siguen sumando todo lo pendiente."""
        self.crear("Lejana", 100)
        resumen = dashboard_selectors.resumen(self.usuario, hoy=HOY)
        self.assertEqual(resumen["total_obligaciones"], 1)
        self.assertGreater(resumen["comprometido"], Decimal("0"))


class MisObligacionesVentanaTests(BaseVentana):
    """§3: la vista "Mis obligaciones" por defecto."""

    def test_incluye_pendiente_dentro_de_30_dias(self):
        self.crear("Dentro de la ventana", 15)
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertContains(respuesta, "Dentro de la ventana")

    def test_excluye_pendiente_fuera_de_la_ventana_por_defecto(self):
        self.crear("Fuera de la ventana", 45)
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertNotContains(respuesta, "Fuera de la ventana")

    def test_vencida_y_no_pagada_sigue_visible_aunque_sea_muy_vieja(self):
        self.crear("Vencida hace mucho", -400)
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertContains(respuesta, "Vencida hace mucho")

    def test_pagada_no_aparece_por_defecto_pero_si_con_el_filtro(self):
        self.crear("Ya la pague", 10, pagada=True)

        respuesta_defecto = self.client.get(reverse("obligaciones:lista"))
        self.assertNotContains(respuesta_defecto, "Ya la pague")

        respuesta_filtrada = self.client.get(reverse("obligaciones:lista"), {"estado": "PAGADA"})
        self.assertContains(respuesta_filtrada, "Ya la pague")

    def test_un_filtro_de_fecha_propio_desactiva_la_ventana_por_completo(self):
        """§3: "Evitar que los filtros de fecha del usuario sean
        sobrescritos silenciosamente por el rango predeterminado."""
        self.crear("Muy lejana", 200)

        respuesta = self.client.get(
            reverse("obligaciones:lista"),
            {"desde": HOY.isoformat(), "hasta": (HOY + timedelta(days=250)).isoformat()},
        )

        self.assertContains(respuesta, "Muy lejana")
        self.assertFalse(respuesta.context["ventana_activa"])

    def test_un_filtro_de_categoria_tambien_desactiva_la_ventana(self):
        self.crear("Lejana con categoria", 200)
        respuesta = self.client.get(
            reverse("obligaciones:lista"), {"categoria": self.categoria.pk}
        )
        self.assertContains(respuesta, "Lejana con categoria")

    def test_el_enlace_ver_todas_desactiva_la_ventana(self):
        self.crear("Lejana de verdad", 200)
        respuesta = self.client.get(reverse("obligaciones:lista"), {"ventana": "todas"})
        self.assertContains(respuesta, "Lejana de verdad")
        self.assertFalse(respuesta.context["ventana_activa"])

    def test_el_contexto_indica_cuando_la_ventana_esta_activa(self):
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertTrue(respuesta.context["ventana_activa"])

    def test_busqueda_de_texto_tambien_desactiva_la_ventana(self):
        self.crear("Netflix lejano", 200)
        respuesta = self.client.get(reverse("obligaciones:lista"), {"q": "netflix"})
        self.assertContains(respuesta, "Netflix lejano")


class CalendarioSinVentanaTests(BaseVentana):
    """§4: el calendario no debe aplicar la ventana de 30 días."""

    def test_el_calendario_muestra_una_obligacion_a_100_dias(self):
        lejana = self.crear("A 100 dias", 100)
        anio, mes = lejana.fecha_vencimiento.year, lejana.fecha_vencimiento.month

        respuesta = self.client.get(
            reverse("dashboard:calendario"), {"anio": anio, "mes": mes}
        )

        self.assertContains(respuesta, f'dia={lejana.fecha_vencimiento.day}')
        self.assertEqual(respuesta.context["cantidad_mes"], 1)

    def test_el_calendario_puede_abrir_el_detalle_de_un_dia_lejano(self):
        lejana = self.crear("Detalle lejano", 100)
        respuesta = self.client.get(
            reverse("dashboard:calendario"),
            {
                "anio": lejana.fecha_vencimiento.year,
                "mes": lejana.fecha_vencimiento.month,
                "dia": lejana.fecha_vencimiento.day,
            },
        )
        self.assertContains(respuesta, "Detalle lejano")


class AislamientoYRegresionTests(BaseVentana):
    """§6/§10: sin regresiones en permisos, logos ni otras pantallas."""

    def test_la_ventana_no_mezcla_obligaciones_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear("De otro usuario", 5, usuario=otro)

        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertNotContains(respuesta, "De otro usuario")

    def test_el_logo_de_marca_sigue_apareciendo_en_la_ventana(self):
        self.crear("Spotify", 5)
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertContains(respuesta, 'title="Spotify"')

    def test_el_detalle_de_una_obligacion_lejana_sigue_siendo_accesible(self):
        """La ventana solo afecta listados; el detalle, por URL directa,
        sigue abriendo cualquier obligación propia sin importar la fecha."""
        lejana = self.crear("Detalle directo", 100)
        respuesta = self.client.get(reverse("obligaciones:detalle", args=[lejana.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Detalle directo")
