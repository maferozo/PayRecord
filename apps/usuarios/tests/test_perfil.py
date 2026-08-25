from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import Empresa, TipoUsuario

Usuario = get_user_model()


class PerfilPersonalTests(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)
        self.url = reverse("usuarios:perfil")

    def test_muestra_los_formularios(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNotNone(respuesta.context["form_perfil"])
        self.assertIsNotNone(respuesta.context["form_configuracion"])
        self.assertIsNone(respuesta.context["form_empresa"])  # cuenta personal

    def test_editar_los_datos_de_la_cuenta(self):
        respuesta = self.client.post(self.url, {
            "seccion": "perfil",
            "perfil-nombre": "María Rodríguez",
            "perfil-email": "maria.nueva@example.com",
        })
        self.assertRedirects(respuesta, self.url)

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.nombre, "María Rodríguez")
        self.assertEqual(self.usuario.email, "maria.nueva@example.com")

    def test_no_puede_tomar_el_correo_de_otro(self):
        Usuario.objects.create_user(
            email="ocupado@example.com", nombre="Otro", password="ClaveSegura123"
        )
        respuesta = self.client.post(self.url, {
            "seccion": "perfil",
            "perfil-nombre": "María",
            "perfil-email": "ocupado@example.com",
        })

        self.assertEqual(respuesta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "maria@example.com")

    def test_conservar_el_propio_correo_no_es_un_duplicado(self):
        respuesta = self.client.post(self.url, {
            "seccion": "perfil",
            "perfil-nombre": "María Actualizada",
            "perfil-email": "maria@example.com",
        })
        self.assertRedirects(respuesta, self.url)

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.nombre, "María Actualizada")

    def test_editar_las_preferencias(self):
        respuesta = self.client.post(self.url, {
            "seccion": "config",
            "config-dias_proximo_vencimiento": "15",
            "config-notificaciones_app": "on",
        })
        self.assertRedirects(respuesta, self.url)

        self.usuario.configuracion.refresh_from_db()
        self.assertEqual(self.usuario.configuracion.dias_proximo_vencimiento, 15)
        self.assertFalse(self.usuario.configuracion.notificaciones_email)

    def test_el_umbral_fuera_de_rango_es_rechazado(self):
        for valor in ("0", "365"):
            with self.subTest(valor=valor):
                self.client.post(self.url, {
                    "seccion": "config",
                    "config-dias_proximo_vencimiento": valor,
                })
                self.usuario.configuracion.refresh_from_db()
                self.assertEqual(self.usuario.configuracion.dias_proximo_vencimiento, 7)

    def test_una_cuenta_personal_no_puede_editar_una_empresa(self):
        """No tiene empresa: la sección se ignora sin romper."""
        respuesta = self.client.post(self.url, {
            "seccion": "empresa",
            "empresa-nombre": "Inventada",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Empresa.objects.exists())

    def test_una_seccion_desconocida_no_rompe(self):
        respuesta = self.client.post(self.url, {"seccion": "inventada"})
        self.assertEqual(respuesta.status_code, 200)


class PerfilEmpresaTests(TestCase):

    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Comercial XYZ", nit="900123456-7")
        self.usuario = Usuario.objects.create_user(
            email="gerente@xyz.com", nombre="Gerente", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=self.empresa,
        )
        self.client.force_login(self.usuario)
        self.url = reverse("usuarios:perfil")

    def test_muestra_el_formulario_de_empresa(self):
        respuesta = self.client.get(self.url)
        self.assertIsNotNone(respuesta.context["form_empresa"])

    def test_editar_los_datos_de_la_empresa(self):
        respuesta = self.client.post(self.url, {
            "seccion": "empresa",
            "empresa-nombre": "Comercial XYZ S.A.S.",
            "empresa-nit": "900123456-7",
            "empresa-telefono": "6041234567",
        })
        self.assertRedirects(respuesta, self.url)

        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.nombre, "Comercial XYZ S.A.S.")
        self.assertEqual(self.empresa.telefono, "6041234567")

    def test_el_tipo_de_cuenta_no_es_editable(self):
        """Riesgo R11: cambiarlo dejaría categorías de otro ámbito."""
        respuesta = self.client.get(self.url)
        self.assertNotIn("tipo_usuario", respuesta.context["form_perfil"].fields)


class CambioContrasenaTests(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)

    def test_cambiar_la_contrasena(self):
        respuesta = self.client.post(reverse("usuarios:password_change"), {
            "old_password": "ClaveSegura123",
            "new_password1": "OtraClaveMejor456",
            "new_password2": "OtraClaveMejor456",
        })
        self.assertRedirects(respuesta, reverse("usuarios:password_change_done"))

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("OtraClaveMejor456"))

    def test_exige_la_contrasena_actual(self):
        respuesta = self.client.post(reverse("usuarios:password_change"), {
            "old_password": "EquivocadaTotalmente",
            "new_password1": "OtraClaveMejor456",
            "new_password2": "OtraClaveMejor456",
        })
        self.assertEqual(respuesta.status_code, 200)

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("ClaveSegura123"))
