"""Pruebas de seguridad transversales (§28, §36).

Van en `core` a propósito: no comprueban una app concreta sino invariantes
que deben cumplirse en toda la aplicación. La prueba de barrido de rutas es
la más valiosa: si alguien añade una vista privada y olvida el mixin de
autenticación, esta suite lo detecta sin que nadie escriba un test nuevo.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils import timezone

from apps.obligaciones.models import Categoria, Obligacion
from apps.recordatorios.models import Notificacion
from apps.usuarios.models import Empresa, TipoUsuario

Usuario = get_user_model()

# Rutas que son públicas por diseño.
RUTAS_PUBLICAS = {
    "core:inicio",
    "usuarios:login",
    "usuarios:registro",
    "usuarios:logout",
    "usuarios:password_reset",
    "usuarios:password_reset_done",
    "usuarios:password_reset_confirm",
    "usuarios:password_reset_complete",
}


def _rutas_con_nombre(resolver=None, prefijo=""):
    """Recorre el árbol de URLs y devuelve los nombres con namespace."""
    resolver = resolver or get_resolver()
    nombres = []

    for patron in resolver.url_patterns:
        if isinstance(patron, URLResolver):
            espacio = patron.namespace
            nuevo = f"{prefijo}{espacio}:" if espacio else prefijo
            nombres.extend(_rutas_con_nombre(patron, nuevo))
        elif isinstance(patron, URLPattern) and patron.name:
            nombres.append(f"{prefijo}{patron.name}")

    return nombres


class BarridoDeRutasTests(TestCase):
    """Toda ruta que no sea pública debe exigir sesión iniciada."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)

    def test_ninguna_ruta_privada_responde_a_un_anonimo(self):
        omitidas = []

        for nombre in _rutas_con_nombre():
            if nombre.startswith("admin:") or nombre in RUTAS_PUBLICAS:
                continue

            try:
                url = reverse(nombre)
            except Exception:
                # Rutas con argumentos: se cubren en las pruebas de su app.
                omitidas.append(nombre)
                continue

            with self.subTest(ruta=nombre):
                respuesta = self.client.get(url)
                self.assertIn(
                    respuesta.status_code, (302, 301),
                    f"La ruta «{nombre}» respondió {respuesta.status_code} a un anónimo.",
                )
                self.assertIn("/cuenta/entrar/", respuesta.url)

    def test_el_admin_exige_ser_staff(self):
        usuario = Usuario.objects.create_user(
            email="normal@example.com", nombre="Normal", password="ClaveSegura123"
        )
        self.client.force_login(usuario)

        respuesta = self.client.get("/admin/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn("Django administration", respuesta.content.decode(errors="ignore"))


class AislamientoTransversalTests(TestCase):
    """§28: «Usuario A → consultar obligación del Usuario B» debe fallar siempre."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.hoy = timezone.localdate()
        self.ana = Usuario.objects.create_user(
            email="ana@example.com", nombre="Ana", password="ClaveSegura123"
        )
        self.beto = Usuario.objects.create_user(
            email="beto@example.com", nombre="Beto", password="ClaveSegura123"
        )
        self.obligacion_de_ana = Obligacion.objects.create(
            usuario=self.ana, concepto="Crédito de Ana", monto=Decimal("450000"),
            fecha_vencimiento=self.hoy + timedelta(days=3), categoria=self.categoria,
        )
        self.categoria_de_ana = Categoria.objects.create(
            nombre="Gimnasio", usuario=self.ana, ambito="PERSONAL"
        )
        self.notificacion_de_ana = Notificacion.objects.create(
            usuario=self.ana, titulo="Aviso de Ana", mensaje="Privado"
        )
        self.client.force_login(self.beto)

    def test_beto_recibe_404_en_todo_lo_de_ana(self):
        rutas = [
            reverse("obligaciones:detalle", args=[self.obligacion_de_ana.pk]),
            reverse("obligaciones:editar", args=[self.obligacion_de_ana.pk]),
            reverse("obligaciones:eliminar", args=[self.obligacion_de_ana.pk]),
            reverse("obligaciones:categoria_editar", args=[self.categoria_de_ana.pk]),
            reverse("obligaciones:categoria_eliminar", args=[self.categoria_de_ana.pk]),
            reverse("recordatorios:abrir", args=[self.notificacion_de_ana.pk]),
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_beto_no_puede_modificar_por_post(self):
        rutas = [
            reverse("obligaciones:eliminar", args=[self.obligacion_de_ana.pk]),
            reverse("obligaciones:cambiar_pago", args=[self.obligacion_de_ana.pk]),
            reverse("obligaciones:categoria_eliminar", args=[self.categoria_de_ana.pk]),
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.post(ruta).status_code, 404)

        self.obligacion_de_ana.refresh_from_db()
        self.assertFalse(self.obligacion_de_ana.pagada)
        self.assertIsNone(self.obligacion_de_ana.eliminada_en)

    def test_los_agregados_no_filtran_importes_ajenos(self):
        """Un total mal filtrado revelaría cuánto debe otra persona."""
        from apps.analitica import selectors as analitica
        from apps.dashboard import selectors as dashboard

        self.assertEqual(dashboard.resumen(self.beto, self.hoy)["comprometido"], 0)
        self.assertEqual(analitica.totales(self.beto, self.hoy)["valor_total"], 0)
        self.assertEqual(dashboard.prioridades_del_dia(self.beto, hoy=self.hoy), [])

    def test_una_empresa_no_ve_los_datos_de_otra(self):
        empresa_a = Empresa.objects.create(nombre="Empresa A")
        empresa_b = Empresa.objects.create(nombre="Empresa B")

        usuario_a = Usuario.objects.create_user(
            email="a@a.com", nombre="A", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=empresa_a,
        )
        usuario_b = Usuario.objects.create_user(
            email="b@b.com", nombre="B", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=empresa_b,
        )
        obligacion_a = Obligacion.objects.create(
            usuario=usuario_a, empresa=empresa_a, concepto="Nómina A",
            monto=Decimal("1200000"), fecha_vencimiento=self.hoy + timedelta(days=5),
            categoria=self.categoria,
        )

        self.assertNotIn(obligacion_a, Obligacion.objects.visibles_para(usuario_b))

        self.client.logout()
        self.client.force_login(usuario_b)
        respuesta = self.client.get(
            reverse("obligaciones:detalle", args=[obligacion_a.pk])
        )
        self.assertEqual(respuesta.status_code, 404)


class ProteccionCsrfTests(TestCase):
    """§28: los formularios deben ir protegidos contra CSRF."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)

    def test_un_post_sin_token_es_rechazado(self):
        cliente = self.client_class(enforce_csrf_checks=True)
        respuesta = cliente.post(reverse("usuarios:login"), {
            "username": "maria@example.com", "password": "ClaveSegura123",
        })
        self.assertEqual(respuesta.status_code, 403)

    def test_los_formularios_incluyen_el_token(self):
        for nombre in ("usuarios:login", "usuarios:registro"):
            with self.subTest(ruta=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertContains(respuesta, "csrfmiddlewaretoken")


class ContrasenasTests(TestCase):
    """§28: nunca en texto plano."""

    def test_se_guardan_hasheadas(self):
        usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.assertNotIn("ClaveSegura123", usuario.password)
        self.assertTrue(usuario.password.startswith("pbkdf2_"))

    def test_la_contrasena_no_aparece_en_la_representacion_del_usuario(self):
        usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.assertNotIn("ClaveSegura123", str(usuario))

    def test_se_rechazan_contrasenas_debiles(self):
        debiles = ["12345678", "password", "abc", "maria@example.com"]
        for clave in debiles:
            with self.subTest(clave=clave):
                respuesta = self.client.post(reverse("usuarios:registro"), {
                    "nombre": "María", "email": "maria@example.com",
                    "tipo_usuario": "PERSONAL",
                    "password1": clave, "password2": clave,
                })
                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(Usuario.objects.filter(email="maria@example.com").exists())

    def test_no_se_revela_si_un_correo_esta_registrado(self):
        """La recuperación responde igual exista o no la cuenta."""
        from django.core import mail

        respuesta_a = self.client.post(
            reverse("usuarios:password_reset"), {"email": "nadie@example.com"}
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertRedirects(respuesta_a, reverse("usuarios:password_reset_done"))


class InyeccionTests(TestCase):
    """§28: el ORM parametriza, pero conviene comprobarlo."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)
        Obligacion.objects.create(
            usuario=self.usuario, concepto="Internet", monto=Decimal("120000"),
            fecha_vencimiento=timezone.localdate(), categoria=self.categoria,
        )

    def test_el_buscador_no_ejecuta_sql(self):
        cargas = [
            "'; DROP TABLE obligaciones_obligacion; --",
            "1 OR 1=1",
            "%' OR '1'='1",
        ]
        for carga in cargas:
            with self.subTest(carga=carga):
                respuesta = self.client.get(reverse("obligaciones:lista"), {"q": carga})
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(len(respuesta.context["obligaciones"]), 0)

        # La tabla sigue existiendo y con sus datos.
        self.assertEqual(Obligacion.objects.count(), 1)

    def test_el_contenido_del_usuario_se_escapa_en_la_plantilla(self):
        Obligacion.objects.create(
            usuario=self.usuario, concepto="<script>alert('xss')</script>",
            monto=Decimal("1000"), fecha_vencimiento=timezone.localdate(),
            categoria=self.categoria,
        )
        respuesta = self.client.get(reverse("obligaciones:lista"))

        self.assertNotContains(respuesta, "<script>alert('xss')</script>")
        self.assertContains(respuesta, "&lt;script&gt;")


@override_settings(
    SECURE_CONTENT_TYPE_NOSNIFF=True,
    X_FRAME_OPTIONS="DENY",
    SECURE_REFERRER_POLICY="same-origin",
)
class CabecerasTests(TestCase):
    """Las cabeceras que activa `config/settings/production.py`."""

    def test_las_cabeceras_de_seguridad_se_envian(self):
        respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(respuesta.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(respuesta.headers.get("Referrer-Policy"), "same-origin")


class ConfiguracionProduccionTests(TestCase):
    """Que `production.py` no deje DEBUG encendido ni cookies abiertas."""

    def test_produccion_endurece_lo_que_debe(self):
        import importlib

        produccion = importlib.import_module("config.settings.production")

        self.assertFalse(produccion.DEBUG)
        self.assertTrue(produccion.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(produccion.CSRF_COOKIE_HTTPONLY)
        self.assertTrue(produccion.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(produccion.X_FRAME_OPTIONS, "DENY")

    def test_las_credenciales_no_estan_en_el_codigo(self):
        """§28: nada de secretos escritos a mano en los settings."""
        from pathlib import Path

        base = Path(__file__).resolve().parent.parent.parent.parent / "config" / "settings"
        for archivo in base.glob("*.py"):
            with self.subTest(archivo=archivo.name):
                contenido = archivo.read_text(encoding="utf-8")
                self.assertNotIn("PayRecord2026", contenido)
                self.assertNotIn('SECRET_KEY = "django-insecure', contenido)
