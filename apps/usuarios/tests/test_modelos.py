from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.usuarios.models import ConfiguracionUsuario, Empresa, TipoUsuario

Usuario = get_user_model()


class UsuarioModeloTests(TestCase):

    def test_crear_usuario_normaliza_el_dominio_del_correo(self):
        usuario = Usuario.objects.create_user(
            email="Maria@Example.COM", nombre="María", password="ClaveSegura123"
        )
        self.assertEqual(usuario.email, "Maria@example.com")

    def test_la_contrasena_se_guarda_hasheada(self):
        """§28: nunca en texto plano."""
        usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.assertNotEqual(usuario.password, "ClaveSegura123")
        self.assertTrue(usuario.password.startswith("pbkdf2_"))
        self.assertTrue(usuario.check_password("ClaveSegura123"))

    def test_crear_usuario_sin_correo_falla(self):
        with self.assertRaises(ValueError):
            Usuario.objects.create_user(email="", nombre="X", password="ClaveSegura123")

    def test_superusuario(self):
        admin = Usuario.objects.create_superuser(
            email="admin@payrecord.local", nombre="Admin", password="ClaveSegura123"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_usuario_nuevo_recibe_configuracion_automatica(self):
        usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.assertTrue(ConfiguracionUsuario.objects.filter(usuario=usuario).exists())
        self.assertEqual(usuario.configuracion.dias_proximo_vencimiento, 7)
        self.assertEqual(usuario.configuracion.dias_recordatorio_default, [7, 3, 1, 0])

    def test_propiedades_de_tipo(self):
        personal = Usuario.objects.create_user(
            email="p@example.com", nombre="Personal", password="ClaveSegura123"
        )
        empresa = Usuario.objects.create_user(
            email="e@example.com",
            nombre="Empresa",
            password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA,
            empresa=Empresa.objects.create(nombre="Comercial XYZ"),
        )
        self.assertTrue(personal.es_personal)
        self.assertFalse(personal.es_empresa)
        self.assertTrue(empresa.es_empresa)
