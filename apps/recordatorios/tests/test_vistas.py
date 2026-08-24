from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.obligaciones.models import Categoria, Obligacion
from apps.recordatorios.models import Notificacion

Usuario = get_user_model()


class BaseVistas(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )
        self.client.force_login(self.usuario)

    def crear_notificacion(self, usuario=None, titulo="Internet vence mañana", leida=False):
        return Notificacion.objects.create(
            usuario=usuario or self.usuario,
            titulo=titulo,
            mensaje="Tu obligación vence pronto.",
            url_destino="/obligaciones/1/",
            leida=leida,
        )


class BandejaTests(BaseVistas):

    def test_muestra_las_notificaciones(self):
        self.crear_notificacion()
        respuesta = self.client.get(reverse("recordatorios:bandeja"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Internet vence mañana")

    def test_exige_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse("recordatorios:bandeja"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/entrar/", respuesta.url)

    def test_no_muestra_notificaciones_de_otro(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear_notificacion(usuario=otro, titulo="Secreto ajeno")

        respuesta = self.client.get(reverse("recordatorios:bandeja"))
        self.assertNotContains(respuesta, "Secreto ajeno")

    def test_filtrar_por_no_leidas(self):
        self.crear_notificacion(titulo="Sin leer", leida=False)
        self.crear_notificacion(titulo="Ya leida", leida=True)

        respuesta = self.client.get(reverse("recordatorios:bandeja"), {"filtro": "no-leidas"})
        self.assertContains(respuesta, "Sin leer")
        self.assertNotContains(respuesta, "Ya leida")

    def test_abrir_marca_como_leida_y_registra_el_momento(self):
        notificacion = self.crear_notificacion()

        respuesta = self.client.get(reverse("recordatorios:abrir", args=[notificacion.pk]))

        notificacion.refresh_from_db()
        self.assertTrue(notificacion.leida)
        self.assertIsNotNone(notificacion.fecha_lectura)  # insumo de §20
        self.assertEqual(respuesta.status_code, 302)

    def test_no_puede_abrir_la_notificacion_de_otro(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        ajena = self.crear_notificacion(usuario=otro)

        respuesta = self.client.get(reverse("recordatorios:abrir", args=[ajena.pk]))

        self.assertEqual(respuesta.status_code, 404)
        ajena.refresh_from_db()
        self.assertFalse(ajena.leida)

    def test_marcar_todas_como_leidas(self):
        for i in range(3):
            self.crear_notificacion(titulo=f"Aviso {i}")

        self.client.post(reverse("recordatorios:leer_todas"))

        self.assertEqual(Notificacion.objects.de(self.usuario).no_leidas().count(), 0)

    def test_marcar_todas_no_afecta_a_otros_usuarios(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        self.crear_notificacion(usuario=otro)

        self.client.post(reverse("recordatorios:leer_todas"))

        self.assertEqual(Notificacion.objects.de(otro).no_leidas().count(), 1)

    def test_marcar_todas_solo_por_post(self):
        self.crear_notificacion()
        self.client.get(reverse("recordatorios:leer_todas"))
        self.assertEqual(Notificacion.objects.de(self.usuario).no_leidas().count(), 1)


class ContadorMenuTests(BaseVistas):

    def test_el_contador_aparece_en_el_menu(self):
        self.crear_notificacion()
        self.crear_notificacion(titulo="Otro aviso")

        respuesta = self.client.get(reverse("recordatorios:bandeja"))
        self.assertEqual(respuesta.context["notificaciones_no_leidas"], 2)

    def test_sin_sesion_no_hay_contador(self):
        self.client.logout()
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertNotIn("notificaciones_no_leidas", respuesta.context)


class FormularioObligacionTests(BaseVistas):
    """Las casillas de recordatorio del formulario (§10, §13)."""

    def datos(self, **extra):
        base = {
            "concepto": "Internet",
            "monto": "120000",
            "fecha_vencimiento": "2026-09-30",
            "categoria": self.categoria.pk,
            "prioridad_usuario": "MEDIA",
            "descripcion": "",
            "enlace_pago": "",
        }
        base.update(extra)
        return base

    def test_al_crear_se_guardan_las_reglas_marcadas(self):
        self.client.post(
            reverse("obligaciones:crear"), self.datos(recordatorios=["7", "1", "0"])
        )
        obligacion = Obligacion.objects.get(concepto="Internet")

        activas = obligacion.reglas_recordatorio.filter(activa=True)
        self.assertEqual(set(activas.values_list("dias_antes", flat=True)), {7, 1, 0})

    def test_sin_marcar_nada_no_se_crean_reglas(self):
        self.client.post(reverse("obligaciones:crear"), self.datos(recordatorios=[]))
        obligacion = Obligacion.objects.get(concepto="Internet")

        self.assertEqual(obligacion.reglas_recordatorio.filter(activa=True).count(), 0)

    def test_un_valor_no_permitido_es_rechazado(self):
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos(recordatorios=["999"])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())

    def test_al_crear_se_proponen_las_preferencias_del_usuario(self):
        configuracion = self.usuario.configuracion
        configuracion.dias_recordatorio_default = [3, 1]
        configuracion.save()

        respuesta = self.client.get(reverse("obligaciones:crear"))
        self.assertEqual(
            respuesta.context["form"].fields["recordatorios"].initial, ["3", "1"]
        )

    def test_al_editar_se_muestran_las_reglas_actuales(self):
        self.client.post(
            reverse("obligaciones:crear"), self.datos(recordatorios=["7", "0"])
        )
        obligacion = Obligacion.objects.get(concepto="Internet")

        respuesta = self.client.get(reverse("obligaciones:editar", args=[obligacion.pk]))
        iniciales = set(respuesta.context["form"].fields["recordatorios"].initial)
        self.assertEqual(iniciales, {"7", "0"})


class CatchUpTests(BaseVistas):
    """§16: el dashboard recupera los avisos que la tarea programada no pudo generar."""

    def test_al_abrir_el_dashboard_se_generan_los_avisos_atrasados(self):
        from apps.recordatorios.models import ConfiguracionRecordatorio, Recordatorio

        hoy = timezone.localdate()
        obligacion = Obligacion.objects.create(
            usuario=self.usuario, concepto="Internet", monto=Decimal("120000"),
            fecha_vencimiento=hoy, categoria=self.categoria,
        )
        ConfiguracionRecordatorio.objects.create(obligacion=obligacion, dias_antes=0)

        self.assertEqual(Recordatorio.objects.count(), 0)
        self.client.get(reverse("dashboard:inicio"))
        self.assertEqual(Recordatorio.objects.count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_recargar_el_dashboard_no_duplica(self):
        from apps.recordatorios.models import ConfiguracionRecordatorio, Recordatorio

        hoy = timezone.localdate()
        obligacion = Obligacion.objects.create(
            usuario=self.usuario, concepto="Internet", monto=Decimal("120000"),
            fecha_vencimiento=hoy, categoria=self.categoria,
        )
        ConfiguracionRecordatorio.objects.create(obligacion=obligacion, dias_antes=0)

        for _ in range(3):
            self.client.get(reverse("dashboard:inicio"))

        self.assertEqual(Recordatorio.objects.count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)


class ProgramadosTests(BaseVistas):

    def test_lista_los_recordatorios_del_usuario(self):
        from apps.recordatorios.models import ConfiguracionRecordatorio
        from apps.recordatorios.services.generacion import generar

        obligacion = Obligacion.objects.create(
            usuario=self.usuario, concepto="Arriendo", monto=Decimal("900000"),
            fecha_vencimiento=date(2026, 8, 25), categoria=self.categoria,
        )
        ConfiguracionRecordatorio.objects.create(obligacion=obligacion, dias_antes=7)
        generar(hoy=date(2026, 8, 18))

        respuesta = self.client.get(reverse("recordatorios:programados"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Arriendo")

    def test_no_lista_los_de_otro_usuario(self):
        from apps.recordatorios.models import ConfiguracionRecordatorio
        from apps.recordatorios.services.generacion import generar

        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        obligacion = Obligacion.objects.create(
            usuario=otro, concepto="Secreto ajeno", monto=Decimal("900000"),
            fecha_vencimiento=date(2026, 8, 25), categoria=self.categoria,
        )
        ConfiguracionRecordatorio.objects.create(obligacion=obligacion, dias_antes=7)
        generar(hoy=date(2026, 8, 18))

        respuesta = self.client.get(reverse("recordatorios:programados"))
        self.assertNotContains(respuesta, "Secreto ajeno")
