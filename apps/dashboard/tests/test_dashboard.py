from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.dashboard import selectors
from apps.obligaciones.models import Categoria, Obligacion
from apps.usuarios.models import Empresa, TipoUsuario

Usuario = get_user_model()


class BaseDashboard(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.servicios = Categoria.objects.get(codigo="servicios")
        cls.creditos = Categoria.objects.get(codigo="creditos")

    def setUp(self):
        self.hoy = timezone.localdate()
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)

    def crear(self, concepto, monto, dias, pagada=False, categoria=None, usuario=None,
              prioridad="MEDIA", proveedor=""):
        return Obligacion.objects.create(
            usuario=usuario or self.usuario,
            concepto=concepto,
            monto=Decimal(monto),
            fecha_vencimiento=self.hoy + timedelta(days=dias),
            categoria=categoria or self.servicios,
            pagada=pagada,
            fecha_pago=self.hoy if pagada else None,
            prioridad_usuario=prioridad,
            proveedor=proveedor,
        )


class ResumenTests(BaseDashboard):
    """§11: conteos y sumas por estado."""

    def test_cuenta_y_suma_cada_estado(self):
        self.crear("Vencida", 100000, -5)
        self.crear("Proxima", 200000, 3)
        self.crear("Pendiente", 300000, 60)
        self.crear("Pagada", 50000, -10, pagada=True)

        datos = selectors.resumen(self.usuario, self.hoy)

        self.assertEqual(datos["vencidas"]["cantidad"], 1)
        self.assertEqual(datos["vencidas"]["total"], Decimal("100000"))
        self.assertEqual(datos["proximas"]["total"], Decimal("200000"))
        self.assertEqual(datos["pendientes"]["total"], Decimal("300000"))
        self.assertEqual(datos["pagadas"]["total"], Decimal("50000"))
        self.assertEqual(datos["total_obligaciones"], 4)

    def test_dinero_comprometido_excluye_lo_pagado(self):
        self.crear("Vencida", 100000, -5)
        self.crear("Proxima", 200000, 3)
        self.crear("Pendiente", 300000, 60)
        self.crear("Pagada", 999999, -10, pagada=True)

        datos = selectors.resumen(self.usuario, self.hoy)
        self.assertEqual(datos["comprometido"], Decimal("600000"))

    def test_sin_obligaciones_devuelve_ceros(self):
        datos = selectors.resumen(self.usuario, self.hoy)
        self.assertEqual(datos["comprometido"], Decimal("0"))
        self.assertEqual(datos["total_obligaciones"], 0)
        self.assertEqual(datos["vencidas"]["cantidad"], 0)

    def test_no_mezcla_datos_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear("De otro", 5000000, 3, usuario=otro)
        self.crear("Mia", 100000, 3)

        datos = selectors.resumen(self.usuario, self.hoy)
        self.assertEqual(datos["comprometido"], Decimal("100000"))

    def test_las_eliminadas_no_cuentan(self):
        obligacion = self.crear("Borrada", 500000, 3)
        obligacion.eliminar_logicamente()
        self.crear("Viva", 100000, 3)

        datos = selectors.resumen(self.usuario, self.hoy)
        self.assertEqual(datos["comprometido"], Decimal("100000"))


class PrioridadesTests(BaseDashboard):
    """§12: qué atender primero."""

    def test_ordena_por_prioridad_no_por_fecha(self):
        self.crear("Lejana barata", 10000, 40, prioridad="BAJA")
        self.crear("Vencida grande", 900000, -3, categoria=self.creditos, prioridad="ALTA")

        prioridades = selectors.prioridades_del_dia(self.usuario, hoy=self.hoy)
        self.assertEqual(prioridades[0][0].concepto, "Vencida grande")

    def test_cada_prioridad_trae_su_motivo(self):
        self.crear("Internet", 120000, 1)

        prioridades = selectors.prioridades_del_dia(self.usuario, hoy=self.hoy)
        _, resultado = prioridades[0]

        self.assertTrue(resultado.motivos)
        self.assertIn("Vence mañana", resultado.motivos)

    def test_las_pagadas_no_aparecen(self):
        self.crear("Pagada", 900000, -3, pagada=True)
        self.crear("Pendiente", 100000, 5)

        prioridades = selectors.prioridades_del_dia(self.usuario, hoy=self.hoy)
        conceptos = [o.concepto for o, _ in prioridades]
        self.assertNotIn("Pagada", conceptos)

    def test_respeta_el_limite(self):
        for i in range(10):
            self.crear(f"Obligación {i}", 100000, i)

        prioridades = selectors.prioridades_del_dia(self.usuario, limite=3, hoy=self.hoy)
        self.assertEqual(len(prioridades), 3)

    def test_sin_pendientes_devuelve_lista_vacia(self):
        self.assertEqual(selectors.prioridades_del_dia(self.usuario, hoy=self.hoy), [])


class ProximasYCategoriasTests(BaseDashboard):

    def test_proximas_ordenadas_por_fecha(self):
        self.crear("Tercera", 100000, 20)
        self.crear("Primera", 100000, 1)
        self.crear("Segunda", 100000, 10)

        proximas = selectors.proximas_obligaciones(self.usuario, hoy=self.hoy)
        self.assertEqual([o.concepto for o in proximas], ["Primera", "Segunda", "Tercera"])

    def test_proximas_excluye_pagadas(self):
        self.crear("Pagada", 100000, 1, pagada=True)
        self.crear("Pendiente", 100000, 5)

        proximas = selectors.proximas_obligaciones(self.usuario, hoy=self.hoy)
        self.assertEqual([o.concepto for o in proximas], ["Pendiente"])

    def test_gasto_por_categoria_agrupa_y_ordena(self):
        self.crear("Luz", 100000, 5, categoria=self.servicios)
        self.crear("Agua", 50000, 6, categoria=self.servicios)
        self.crear("Préstamo", 900000, 7, categoria=self.creditos)

        filas = selectors.gasto_por_categoria(self.usuario, hoy=self.hoy)

        self.assertEqual(filas[0]["categoria__nombre"], "Créditos")
        self.assertEqual(filas[0]["total"], Decimal("900000"))
        self.assertEqual(filas[1]["total"], Decimal("150000"))
        self.assertEqual(filas[1]["cantidad"], 2)


class ProveedoresTests(BaseDashboard):
    """§26: bloque exclusivo del dashboard empresarial."""

    def test_una_cuenta_personal_no_tiene_proveedores(self):
        self.crear("Algo", 100000, 5, proveedor="Proveedor XYZ")
        self.assertEqual(selectors.principales_proveedores(self.usuario, hoy=self.hoy), [])

    def test_una_cuenta_empresa_agrupa_por_proveedor(self):
        empresa = Empresa.objects.create(nombre="Comercial XYZ")
        gerente = Usuario.objects.create_user(
            email="gerente@xyz.com", nombre="Gerente", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=empresa,
        )
        for concepto, monto, proveedor in [
            ("Factura 1", 500000, "Distribuidora XYZ"),
            ("Factura 2", 300000, "Distribuidora XYZ"),
            ("Factura 3", 100000, "Papelería ABC"),
        ]:
            Obligacion.objects.create(
                usuario=gerente, empresa=empresa, concepto=concepto, monto=Decimal(monto),
                fecha_vencimiento=self.hoy + timedelta(days=5), categoria=self.servicios,
                proveedor=proveedor,
            )

        filas = selectors.principales_proveedores(gerente, hoy=self.hoy)
        self.assertEqual(filas[0]["proveedor"], "Distribuidora XYZ")
        self.assertEqual(filas[0]["total"], Decimal("800000"))
        self.assertEqual(filas[0]["cantidad"], 2)


class VistaDashboardTests(BaseDashboard):

    def test_responde_200_y_usa_su_plantilla(self):
        respuesta = self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "dashboard/inicio.html")

    def test_exige_sesion_iniciada(self):
        self.client.logout()
        respuesta = self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/entrar/", respuesta.url)

    def test_muestra_el_dinero_comprometido_formateado(self):
        self.crear("Crédito", 450000, 2)
        respuesta = self.client.get(reverse("dashboard:inicio"))
        self.assertContains(respuesta, "$450.000")

    def test_muestra_los_motivos_de_prioridad(self):
        self.crear("Crédito", 450000, 1)
        respuesta = self.client.get(reverse("dashboard:inicio"))
        self.assertContains(respuesta, "Vence mañana")

    def test_no_filtra_obligaciones_de_otro_usuario(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear("Secreto de otro", 100000, 3, usuario=otro)

        respuesta = self.client.get(reverse("dashboard:inicio"))
        self.assertNotContains(respuesta, "Secreto de otro")

    def test_la_portada_lleva_al_dashboard_si_hay_sesion(self):
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertRedirects(respuesta, reverse("dashboard:inicio"))

    def test_la_portada_publica_sigue_visible_sin_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertEqual(respuesta.status_code, 200)
