from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import Empresa, TipoUsuario

Usuario = get_user_model()


class RegistroTests(TestCase):
    """Casos mínimos de §36 para el registro."""

    url = None

    def setUp(self):
        self.url = reverse("usuarios:registro")
        self.datos = {
            "nombre": "María Rodríguez",
            "email": "maria@example.com",
            "tipo_usuario": TipoUsuario.PERSONAL,
            "password1": "ClaveSegura123",
            "password2": "ClaveSegura123",
        }

    def test_registro_correcto_crea_usuario_y_lo_autentica(self):
        respuesta = self.client.post(self.url, self.datos)
        self.assertRedirects(respuesta, reverse("core:inicio"))

        usuario = Usuario.objects.get(email="maria@example.com")
        self.assertEqual(usuario.nombre, "María Rodríguez")
        self.assertTrue(usuario.es_personal)
        self.assertIsNone(usuario.empresa)
        self.assertIn("_auth_user_id", self.client.session)

    def test_correo_duplicado_es_rechazado(self):
        Usuario.objects.create_user(
            email="maria@example.com", nombre="Otra María", password="ClaveSegura123"
        )
        respuesta = self.client.post(self.url, self.datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertFormError(
            respuesta.context["form"], "email",
            "Ya existe una cuenta registrada con este correo.",
        )
        self.assertEqual(Usuario.objects.filter(email="maria@example.com").count(), 1)

    def test_correo_duplicado_ignorando_mayusculas(self):
        Usuario.objects.create_user(
            email="maria@example.com", nombre="Otra", password="ClaveSegura123"
        )
        self.datos["email"] = "MARIA@example.com"
        respuesta = self.client.post(self.url, self.datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Usuario.objects.count(), 1)

    def test_contrasenas_que_no_coinciden(self):
        self.datos["password2"] = "OtraClave456"
        respuesta = self.client.post(self.url, self.datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.exists())

    def test_contrasena_demasiado_corta(self):
        self.datos["password1"] = self.datos["password2"] = "abc12"
        respuesta = self.client.post(self.url, self.datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.exists())

    def test_registro_empresa_crea_la_empresa_y_la_enlaza(self):
        self.datos.update({
            "tipo_usuario": TipoUsuario.EMPRESA,
            "nombre_empresa": "Comercial XYZ",
            "nit": "900123456-7",
        })
        respuesta = self.client.post(self.url, self.datos)
        self.assertRedirects(respuesta, reverse("core:inicio"))

        usuario = Usuario.objects.get(email="maria@example.com")
        self.assertTrue(usuario.es_empresa)
        self.assertIsNotNone(usuario.empresa)
        self.assertEqual(usuario.empresa.nombre, "Comercial XYZ")
        self.assertEqual(Empresa.objects.count(), 1)

    def test_registro_empresa_sin_nombre_de_empresa_falla(self):
        self.datos["tipo_usuario"] = TipoUsuario.EMPRESA
        respuesta = self.client.post(self.url, self.datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.exists())
        # No debe quedar una empresa huérfana (el save es atómico)
        self.assertFalse(Empresa.objects.exists())


class LoginTests(TestCase):
    """Casos mínimos de §36 para el inicio de sesión."""

    def setUp(self):
        self.url = reverse("usuarios:login")
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )

    def test_login_correcto(self):
        respuesta = self.client.post(
            self.url, {"username": "maria@example.com", "password": "ClaveSegura123"}
        )
        self.assertRedirects(respuesta, reverse("core:inicio"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_contrasena_incorrecta(self):
        respuesta = self.client.post(
            self.url, {"username": "maria@example.com", "password": "ClaveEquivocada"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(respuesta, "El correo o la contraseña no son correctos.")

    def test_correo_inexistente(self):
        respuesta = self.client.post(
            self.url, {"username": "nadie@example.com", "password": "ClaveSegura123"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_desactivado_no_puede_entrar(self):
        """§27: el administrador puede desactivar cuentas."""
        self.usuario.is_active = False
        self.usuario.save()

        respuesta = self.client.post(
            self.url, {"username": "maria@example.com", "password": "ClaveSegura123"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_cierra_la_sesion(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("usuarios:logout"))
        self.assertRedirects(respuesta, reverse("core:inicio"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProteccionDeRutasTests(TestCase):
    """§28: las rutas privadas exigen sesión iniciada."""

    def test_perfil_anonimo_redirige_al_login(self):
        respuesta = self.client.get(reverse("usuarios:perfil"))
        self.assertRedirects(
            respuesta, f"{reverse('usuarios:login')}?next={reverse('usuarios:perfil')}"
        )

    def test_perfil_autenticado_responde_200(self):
        usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("usuarios:perfil"))
        self.assertEqual(respuesta.status_code, 200)


class RecuperacionContrasenaTests(TestCase):

    def test_se_envia_correo_a_una_cuenta_existente(self):
        Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        respuesta = self.client.post(
            reverse("usuarios:password_reset"), {"email": "maria@example.com"}
        )
        self.assertRedirects(respuesta, reverse("usuarios:password_reset_done"))

        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("PAYRECORD", mail.outbox[0].subject)

    def test_correo_inexistente_no_revela_nada(self):
        """No debe filtrar qué correos están registrados."""
        respuesta = self.client.post(
            reverse("usuarios:password_reset"), {"email": "nadie@example.com"}
        )
        self.assertRedirects(respuesta, reverse("usuarios:password_reset_done"))

        from django.core import mail
        self.assertEqual(len(mail.outbox), 0)
