from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.obligaciones.models import Categoria, Obligacion
from apps.obligaciones.services import proveedores
from apps.usuarios.models import Empresa, TipoUsuario

Usuario = get_user_model()


class BaseProveedores(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.hoy = timezone.localdate()
        self.empresa = Empresa.objects.create(nombre="Comercial XYZ")
        self.gerente = Usuario.objects.create_user(
            email="gerente@xyz.com", nombre="Gerente", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=self.empresa,
        )
        self.client.force_login(self.gerente)

    def crear(self, concepto, monto, dias, proveedor="", pagada=False, usuario=None):
        propietario = usuario or self.gerente
        return Obligacion.objects.create(
            usuario=propietario,
            empresa=propietario.empresa,
            concepto=concepto,
            monto=Decimal(monto),
            fecha_vencimiento=self.hoy + timedelta(days=dias),
            categoria=self.categoria,
            proveedor=proveedor,
            pagada=pagada,
            fecha_pago=self.hoy if pagada else None,
        )


class NormalizacionTests(BaseProveedores):
    """D4: el campo de texto se mantiene, pero se evita que se multiplique."""

    def test_limpia_espacios_sobrantes(self):
        self.assertEqual(
            proveedores.normalizar("  Distribuidora   XYZ  ", self.gerente),
            "Distribuidora XYZ",
        )

    def test_reutiliza_la_grafia_ya_usada(self):
        self.crear("Factura 1", 100000, 5, proveedor="Claro")

        self.assertEqual(proveedores.normalizar("claro", self.gerente), "Claro")
        self.assertEqual(proveedores.normalizar("  CLARO ", self.gerente), "Claro")

    def test_un_proveedor_nuevo_se_respeta(self):
        self.assertEqual(proveedores.normalizar("Movistar", self.gerente), "Movistar")

    def test_vacio_sigue_vacio(self):
        self.assertEqual(proveedores.normalizar("", self.gerente), "")
        self.assertEqual(proveedores.normalizar("   ", self.gerente), "")
        self.assertEqual(proveedores.normalizar(None, self.gerente), "")

    def test_no_reutiliza_la_grafia_de_otra_empresa(self):
        otra = Empresa.objects.create(nombre="Otra")
        ajeno = Usuario.objects.create_user(
            email="otro@otra.com", nombre="Otro", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=otra,
        )
        self.crear("Suya", 100000, 5, proveedor="Claro", usuario=ajeno)

        self.assertEqual(proveedores.normalizar("claro", self.gerente), "claro")

    def test_el_formulario_normaliza_al_guardar(self):
        self.crear("Factura 1", 100000, 5, proveedor="Distribuidora XYZ")

        self.client.post(reverse("obligaciones:crear"), {
            "concepto": "Factura 2",
            "monto": "200000",
            "fecha_vencimiento": (self.hoy + timedelta(days=10)).isoformat(),
            "categoria": self.categoria.pk,
            "prioridad_usuario": "MEDIA",
            "descripcion": "", "enlace_pago": "",
            "proveedor": "  distribuidora xyz ",
            "referencia": "",
            "recordatorios": [],
        })

        self.assertEqual(
            Obligacion.objects.get(concepto="Factura 2").proveedor, "Distribuidora XYZ"
        )


class SugerenciasTests(BaseProveedores):

    def test_devuelve_los_ya_usados_sin_repetir(self):
        self.crear("F1", 100000, 5, proveedor="Claro")
        self.crear("F2", 100000, 6, proveedor="Claro")
        self.crear("F3", 100000, 7, proveedor="Movistar")
        self.crear("F4", 100000, 8, proveedor="")

        lista = proveedores.sugerencias(self.gerente)
        self.assertEqual(lista, ["Claro", "Movistar"])

    def test_una_cuenta_personal_no_recibe_sugerencias(self):
        personal = Usuario.objects.create_user(
            email="p@example.com", nombre="Personal", password="ClaveSegura123"
        )
        self.assertEqual(proveedores.sugerencias(personal), [])

    def test_el_formulario_las_expone(self):
        self.crear("F1", 100000, 5, proveedor="Claro")
        respuesta = self.client.get(reverse("obligaciones:crear"))
        self.assertIn("Claro", respuesta.context["form"].sugerencias_proveedor)


class ResumenTests(BaseProveedores):

    def test_agrupa_y_calcula_cada_columna(self):
        self.crear("F1", 500000, 5, proveedor="Claro")
        self.crear("F2", 300000, -3, proveedor="Claro")
        self.crear("F3", 100000, -10, proveedor="Claro", pagada=True)
        self.crear("F4", 200000, 5, proveedor="Movistar")

        filas = {f["proveedor"]: f for f in proveedores.resumen(self.gerente, self.hoy)}

        claro = filas["Claro"]
        self.assertEqual(claro["cantidad"], 3)
        self.assertEqual(claro["total"], Decimal("900000"))
        self.assertEqual(claro["pendiente"], Decimal("800000"))
        self.assertEqual(claro["pagado"], Decimal("100000"))
        self.assertEqual(claro["vencido"], Decimal("300000"))

    def test_ordena_por_lo_pendiente(self):
        self.crear("F1", 100000, 5, proveedor="Pequeño")
        self.crear("F2", 900000, 5, proveedor="Grande")

        filas = proveedores.resumen(self.gerente, self.hoy)
        self.assertEqual(filas[0]["proveedor"], "Grande")

    def test_excluye_las_obligaciones_sin_proveedor(self):
        self.crear("Sin proveedor", 100000, 5, proveedor="")
        self.assertEqual(proveedores.resumen(self.gerente, self.hoy), [])

    def test_no_incluye_proveedores_de_otra_empresa(self):
        otra = Empresa.objects.create(nombre="Otra")
        ajeno = Usuario.objects.create_user(
            email="otro@otra.com", nombre="Otro", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=otra,
        )
        self.crear("Suya", 100000, 5, proveedor="Secreto", usuario=ajeno)

        filas = proveedores.resumen(self.gerente, self.hoy)
        self.assertEqual(filas, [])


class VistaProveedoresTests(BaseProveedores):

    def test_lista_los_proveedores(self):
        self.crear("F1", 500000, 5, proveedor="Distribuidora XYZ")

        respuesta = self.client.get(reverse("obligaciones:proveedor_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Distribuidora XYZ")

    def test_una_cuenta_personal_es_redirigida(self):
        """§26: la sección no aplica al escenario personal."""
        self.client.logout()
        personal = Usuario.objects.create_user(
            email="p@example.com", nombre="Personal", password="ClaveSegura123"
        )
        self.client.force_login(personal)

        respuesta = self.client.get(reverse("obligaciones:proveedor_lista"))
        self.assertRedirects(respuesta, reverse("dashboard:inicio"))

    def test_exige_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse("obligaciones:proveedor_lista"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/entrar/", respuesta.url)

    def test_avisa_de_las_obligaciones_sin_proveedor(self):
        self.crear("Con proveedor", 100000, 5, proveedor="Claro")
        self.crear("Sin proveedor", 100000, 5, proveedor="")

        respuesta = self.client.get(reverse("obligaciones:proveedor_lista"))
        self.assertEqual(respuesta.context["sin_proveedor"], 1)

    def test_detalle_de_un_proveedor(self):
        self.crear("Factura 001", 500000, 5, proveedor="Claro")
        self.crear("De otro", 200000, 5, proveedor="Movistar")

        respuesta = self.client.get(
            reverse("obligaciones:proveedor_detalle", args=["Claro"])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Factura 001")
        self.assertNotContains(respuesta, "De otro")
        self.assertEqual(respuesta.context["pendiente"], Decimal("500000"))

    def test_el_detalle_no_filtra_datos_de_otra_empresa(self):
        otra = Empresa.objects.create(nombre="Otra")
        ajeno = Usuario.objects.create_user(
            email="otro@otra.com", nombre="Otro", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=otra,
        )
        self.crear("Secreto ajeno", 100000, 5, proveedor="Claro", usuario=ajeno)

        respuesta = self.client.get(
            reverse("obligaciones:proveedor_detalle", args=["Claro"])
        )
        self.assertNotContains(respuesta, "Secreto ajeno")
