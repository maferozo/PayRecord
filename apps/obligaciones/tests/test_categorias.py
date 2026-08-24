from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.obligaciones.enums import AmbitoCategoria
from apps.obligaciones.models import Categoria
from apps.usuarios.models import Empresa, TipoUsuario

Usuario = get_user_model()


def crear_personal(email="personal@example.com"):
    return Usuario.objects.create_user(email=email, nombre="Personal", password="ClaveSegura123")


def crear_empresa(email="empresa@example.com"):
    return Usuario.objects.create_user(
        email=email,
        nombre="Empresa",
        password="ClaveSegura123",
        tipo_usuario=TipoUsuario.EMPRESA,
        empresa=Empresa.objects.create(nombre="Comercial XYZ"),
    )


class CargarCategoriasTests(TestCase):
    """El catálogo predeterminado de §8."""

    def test_carga_el_catalogo_completo(self):
        call_command("cargar_categorias", verbosity=0)
        self.assertEqual(Categoria.objects.predeterminadas().count(), 13)

    def test_el_comando_es_idempotente(self):
        call_command("cargar_categorias", verbosity=0)
        call_command("cargar_categorias", verbosity=0)
        call_command("cargar_categorias", verbosity=0)
        self.assertEqual(Categoria.objects.predeterminadas().count(), 13)

    def test_las_predeterminadas_no_tienen_usuario(self):
        call_command("cargar_categorias", verbosity=0)
        self.assertFalse(Categoria.objects.predeterminadas().filter(usuario__isnull=False).exists())

    def test_las_categorias_criticas_pesan_mas(self):
        """El peso alimenta el algoritmo de prioridades (§12)."""
        call_command("cargar_categorias", verbosity=0)
        self.assertEqual(Categoria.objects.get(codigo="creditos").peso_prioridad, 5)
        self.assertEqual(Categoria.objects.get(codigo="seguridad-social").peso_prioridad, 5)
        self.assertEqual(Categoria.objects.get(codigo="otros").peso_prioridad, 0)


class DisponiblesParaTests(TestCase):
    """Qué categorías ve cada tipo de cuenta."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)

    def test_personal_no_ve_categorias_de_empresa(self):
        usuario = crear_personal()
        nombres = set(Categoria.objects.disponibles_para(usuario).values_list("nombre", flat=True))

        self.assertIn("Vivienda", nombres)
        self.assertIn("Servicios", nombres)      # ámbito AMBOS
        self.assertNotIn("Nómina", nombres)
        self.assertNotIn("Proveedores", nombres)

    def test_empresa_no_ve_categorias_personales(self):
        usuario = crear_empresa()
        nombres = set(Categoria.objects.disponibles_para(usuario).values_list("nombre", flat=True))

        self.assertIn("Nómina", nombres)
        self.assertIn("Servicios", nombres)      # ámbito AMBOS
        self.assertNotIn("Suscripciones", nombres)
        self.assertNotIn("Vivienda", nombres)

    def test_las_compartidas_aparecen_en_los_dos_ambitos(self):
        personal = crear_personal()
        empresa = crear_empresa()
        for codigo in ("servicios", "creditos", "impuestos", "otros"):
            categoria = Categoria.objects.get(codigo=codigo)
            self.assertEqual(categoria.ambito, AmbitoCategoria.AMBOS)
            self.assertIn(categoria, Categoria.objects.disponibles_para(personal))
            self.assertIn(categoria, Categoria.objects.disponibles_para(empresa))

    def test_una_categoria_inactiva_no_aparece(self):
        usuario = crear_personal()
        categoria = Categoria.objects.get(codigo="salud")
        categoria.activa = False
        categoria.save()
        self.assertNotIn(categoria, Categoria.objects.disponibles_para(usuario))


class AislamientoEntreUsuariosTests(TestCase):
    """§28: un usuario nunca ve ni toca datos de otro."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)

    def setUp(self):
        self.ana = crear_personal("ana@example.com")
        self.beto = crear_personal("beto@example.com")
        self.categoria_de_ana = Categoria.objects.create(
            nombre="Gimnasio", usuario=self.ana, ambito=AmbitoCategoria.PERSONAL
        )

    def test_beto_no_ve_la_categoria_de_ana(self):
        disponibles = Categoria.objects.disponibles_para(self.beto)
        self.assertNotIn(self.categoria_de_ana, disponibles)

    def test_ana_si_ve_la_suya(self):
        self.assertIn(self.categoria_de_ana, Categoria.objects.disponibles_para(self.ana))

    def test_beto_no_puede_editar_la_categoria_de_ana(self):
        self.client.force_login(self.beto)
        respuesta = self.client.get(f"/categorias/{self.categoria_de_ana.pk}/editar/")
        self.assertEqual(respuesta.status_code, 404)

    def test_beto_no_puede_eliminar_la_categoria_de_ana(self):
        self.client.force_login(self.beto)
        respuesta = self.client.post(f"/categorias/{self.categoria_de_ana.pk}/eliminar/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Categoria.objects.filter(pk=self.categoria_de_ana.pk).exists())

    def test_nadie_puede_editar_una_predeterminada(self):
        predeterminada = Categoria.objects.get(codigo="vivienda")
        self.client.force_login(self.ana)
        respuesta = self.client.get(f"/categorias/{predeterminada.pk}/editar/")
        self.assertEqual(respuesta.status_code, 404)

    def test_nadie_puede_eliminar_una_predeterminada(self):
        predeterminada = Categoria.objects.get(codigo="vivienda")
        self.client.force_login(self.ana)
        respuesta = self.client.post(f"/categorias/{predeterminada.pk}/eliminar/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Categoria.objects.filter(pk=predeterminada.pk).exists())


class CrudCategoriasTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)

    def test_crear_categoria_propia(self):
        respuesta = self.client.post(
            "/categorias/nueva/",
            {"nombre": "Mascotas", "color": "#10B981", "icono": "bi-tag", "peso_prioridad": 2},
        )
        self.assertRedirects(respuesta, "/categorias/")

        categoria = Categoria.objects.get(nombre="Mascotas")
        self.assertEqual(categoria.usuario, self.usuario)
        self.assertEqual(categoria.ambito, AmbitoCategoria.PERSONAL)
        self.assertIsNone(categoria.codigo)

    def test_la_categoria_de_una_cuenta_empresa_nace_con_ambito_empresa(self):
        self.client.logout()
        self.client.force_login(crear_empresa())
        self.client.post(
            "/categorias/nueva/",
            {"nombre": "Fletes", "color": "#2563EB", "icono": "bi-truck", "peso_prioridad": 3},
        )
        self.assertEqual(Categoria.objects.get(nombre="Fletes").ambito, AmbitoCategoria.EMPRESA)

    def test_no_puede_repetir_el_nombre_de_una_propia(self):
        Categoria.objects.create(
            nombre="Mascotas", usuario=self.usuario, ambito=AmbitoCategoria.PERSONAL
        )
        respuesta = self.client.post(
            "/categorias/nueva/",
            {"nombre": "mascotas", "color": "#10B981", "icono": "bi-tag", "peso_prioridad": 2},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Categoria.objects.filter(usuario=self.usuario).count(), 1)

    def test_no_puede_chocar_con_una_predeterminada(self):
        respuesta = self.client.post(
            "/categorias/nueva/",
            {"nombre": "Vivienda", "color": "#10B981", "icono": "bi-tag", "peso_prioridad": 2},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Categoria.objects.filter(usuario=self.usuario).exists())

    def test_peso_fuera_de_rango_es_rechazado(self):
        respuesta = self.client.post(
            "/categorias/nueva/",
            {"nombre": "Mascotas", "color": "#10B981", "icono": "bi-tag", "peso_prioridad": 9},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Categoria.objects.filter(nombre="Mascotas").exists())

    def test_editar_y_eliminar_una_propia(self):
        categoria = Categoria.objects.create(
            nombre="Mascotas", usuario=self.usuario, ambito=AmbitoCategoria.PERSONAL
        )
        self.client.post(
            f"/categorias/{categoria.pk}/editar/",
            {"nombre": "Veterinario", "color": "#DC2626", "icono": "bi-heart-pulse",
             "peso_prioridad": 4},
        )
        categoria.refresh_from_db()
        self.assertEqual(categoria.nombre, "Veterinario")
        self.assertEqual(categoria.peso_prioridad, 4)

        self.client.post(f"/categorias/{categoria.pk}/eliminar/")
        self.assertFalse(Categoria.objects.filter(pk=categoria.pk).exists())

    def test_la_lista_exige_sesion_iniciada(self):
        self.client.logout()
        respuesta = self.client.get("/categorias/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/entrar/", respuesta.url)
