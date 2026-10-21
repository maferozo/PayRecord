"""Pruebas del canal de correo real (§14b) y de la tarea diaria (§15, §16).

Django cambia automáticamente EMAIL_BACKEND al backend en memoria
(`locmem`) durante las pruebas, así que `send_mail()` nunca toca una red de
verdad: los mensajes "enviados" se pueden inspeccionar en
`django.core.mail.outbox`.
"""

import datetime
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.obligaciones.models import Categoria, Obligacion
from apps.recordatorios.enums import CanalNotificacion, EstadoRecordatorio
from apps.recordatorios.models import ConfiguracionRecordatorio, Recordatorio
from apps.recordatorios.services.generacion import aplicar_reglas, procesar

Usuario = get_user_model()

HOY = date(2026, 8, 18)
VENCIMIENTO = date(2026, 8, 25)  # 7 días después de HOY


class BaseCorreo(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )

    def activar_correo(self, usuario=None):
        usuario = usuario or self.usuario
        usuario.configuracion.notificaciones_email = True
        usuario.configuracion.save(update_fields=["notificaciones_email"])
        return usuario

    def crear_obligacion(self, vencimiento=VENCIMIENTO, concepto="Internet",
                         pagada=False, usuario=None):
        return Obligacion.objects.create(
            usuario=usuario or self.usuario,
            concepto=concepto,
            monto=Decimal("120000"),
            fecha_vencimiento=vencimiento,
            categoria=self.categoria,
            pagada=pagada,
        )

    def crear_regla_email(self, obligacion, dias):
        return ConfiguracionRecordatorio.objects.create(
            obligacion=obligacion, dias_antes=dias, canal=CanalNotificacion.EMAIL
        )


class EnvioRealDeCorreoTests(BaseCorreo):
    """Los 10 escenarios obligatorios de la Fase 4 para notificaciones."""

    def test_1_recordatorio_un_dia_antes_envia_correo(self):
        # El asunto describe la situación real al momento de entregar (igual
        # que CanalInApp._titulo), así que se usa la fecha real de hoy, no
        # la fecha simulada de generación.
        hoy = timezone.localdate()
        obligacion = self.crear_obligacion(vencimiento=hoy + timedelta(days=1))
        self.crear_regla_email(obligacion, 1)

        resultado = procesar(hoy=hoy)

        self.assertEqual(resultado["enviados"], 1)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["maria@example.com"])
        self.assertIn("Internet", correo.subject)
        self.assertIn("mañana", correo.subject.lower())

    def test_2_recordatorio_el_dia_del_vencimiento_envia_correo(self):
        hoy = timezone.localdate()
        obligacion = self.crear_obligacion(vencimiento=hoy)
        self.crear_regla_email(obligacion, 0)

        resultado = procesar(hoy=hoy)

        self.assertEqual(resultado["enviados"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("vence hoy", mail.outbox[0].subject.lower())

    def test_3_ambas_opciones_simultaneas_envian_dos_correos(self):
        obligacion = self.crear_obligacion(vencimiento=HOY + timedelta(days=1))
        self.crear_regla_email(obligacion, 1)
        self.crear_regla_email(obligacion, 0)

        # El de "0 días antes" todavía no toca (vence mañana, no hoy).
        resultado = procesar(hoy=HOY)
        self.assertEqual(resultado["enviados"], 1)

        # Al día siguiente, el segundo aviso se entrega.
        resultado = procesar(hoy=HOY + timedelta(days=1))
        self.assertEqual(resultado["enviados"], 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_4_obligacion_sin_notificaciones_no_genera_nada(self):
        self.crear_obligacion(vencimiento=HOY)  # sin reglas de ningún canal

        resultado = procesar(hoy=HOY)

        self.assertEqual(resultado, {"creados": 0, "enviados": 0, "errores": 0})
        self.assertEqual(len(mail.outbox), 0)

    def test_5_obligacion_pagada_no_genera_correo(self):
        obligacion = self.crear_obligacion(vencimiento=HOY, pagada=True)
        self.crear_regla_email(obligacion, 0)

        procesar(hoy=HOY)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Recordatorio.objects.count(), 0)

    def test_6_obligacion_eliminada_no_genera_correo(self):
        """PayRecord no tiene un estado "cancelada" propio de la obligación
        (solo pagada / sin pagar); el equivalente es el borrado lógico."""
        obligacion = self.crear_obligacion(vencimiento=HOY)
        self.crear_regla_email(obligacion, 0)
        obligacion.eliminar_logicamente()

        procesar(hoy=HOY)

        self.assertEqual(len(mail.outbox), 0)

    def test_7_ejecucion_repetida_no_duplica_correos(self):
        obligacion = self.crear_obligacion(vencimiento=HOY)
        self.crear_regla_email(obligacion, 0)

        procesar(hoy=HOY)
        procesar(hoy=HOY)
        procesar(hoy=HOY)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Recordatorio.objects.count(), 1)

    def test_8_error_del_proveedor_no_marca_como_enviado(self):
        obligacion = self.crear_obligacion(vencimiento=HOY)
        self.crear_regla_email(obligacion, 0)

        with patch(
            "apps.recordatorios.services.canales.send_mail",
            side_effect=Exception("Conexión SMTP rechazada"),
        ):
            resultado = procesar(hoy=HOY)

        self.assertEqual(resultado["enviados"], 0)
        self.assertEqual(resultado["errores"], 1)
        self.assertEqual(len(mail.outbox), 0)
        recordatorio = Recordatorio.objects.get()
        self.assertEqual(recordatorio.estado, EstadoRecordatorio.ERROR)
        self.assertIn("Conexión SMTP rechazada", recordatorio.detalle_error)

        # Y si el proveedor se recupera después, el reintento sí entrega:
        # un recordatorio en ERROR no queda "atascado" para siempre, porque
        # vuelve a aparecer en `vencidos()` (solo excluye PENDIENTE).
        recordatorio.estado = EstadoRecordatorio.PENDIENTE
        recordatorio.save(update_fields=["estado"])
        resultado = procesar(hoy=HOY)
        self.assertEqual(resultado["enviados"], 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_9_respeta_la_zona_horaria_de_bogota(self):
        """11:30 p.m. en Bogotá ya es la madrugada del día siguiente en
        UTC. `timezone.localdate()` — lo que usa toda la generación de
        recordatorios cuando no se le pasa una fecha explícita — debe
        devolver el día de Bogotá, no el de UTC."""
        instante_utc = datetime.datetime(2026, 8, 19, 4, 30, tzinfo=datetime.timezone.utc)
        with patch("django.utils.timezone.now", return_value=instante_utc):
            hoy_bogota = timezone.localdate()

        self.assertEqual(hoy_bogota, date(2026, 8, 18))

    def test_10_editar_conserva_las_preferencias_de_notificacion(self):
        """Cubierto también a nivel de formulario en
        FormularioObligacionCorreoTests; aquí se prueba el servicio."""
        obligacion = self.crear_obligacion(vencimiento=HOY + timedelta(days=1))
        aplicar_reglas(obligacion, [1, 0], canal=CanalNotificacion.EMAIL)

        # "Editar" sin tocar las casillas: se vuelve a aplicar la misma lista.
        aplicar_reglas(obligacion, [1, 0], canal=CanalNotificacion.EMAIL)

        activas = obligacion.reglas_recordatorio.filter(
            canal=CanalNotificacion.EMAIL, activa=True
        )
        self.assertEqual(set(activas.values_list("dias_antes", flat=True)), {1, 0})


class CanalEmailUnitarioTests(BaseCorreo):
    """El canal en sí, sin pasar por el generador."""

    def test_sin_correo_registrado_lanza_error_claro(self):
        from apps.recordatorios.services.canales import CanalEmail, CanalNoDisponible

        self.usuario.email = ""
        obligacion = self.crear_obligacion()
        recordatorio = Recordatorio.objects.create(
            obligacion=obligacion, dias_antes=0, fecha_programada=HOY,
            canal=CanalNotificacion.EMAIL,
        )

        with self.assertRaises(CanalNoDisponible):
            CanalEmail().enviar(recordatorio)

    def test_incluye_el_enlace_de_pago_cuando_existe(self):
        obligacion = Obligacion.objects.create(
            usuario=self.usuario, concepto="Internet", monto=Decimal("120000"),
            fecha_vencimiento=HOY, categoria=self.categoria,
            enlace_pago="https://pagos.miempresa.com/factura",
        )
        self.crear_regla_email(obligacion, 0)

        procesar(hoy=HOY)

        self.assertIn("https://pagos.miempresa.com/factura", mail.outbox[0].body)

    def test_no_menciona_enlace_cuando_no_hay(self):
        obligacion = self.crear_obligacion(vencimiento=HOY)  # sin enlace_pago
        self.crear_regla_email(obligacion, 0)

        procesar(hoy=HOY)

        self.assertNotIn("Enlace de pago", mail.outbox[0].body)

    def test_el_remitente_es_el_configurado(self):
        from django.conf import settings

        obligacion = self.crear_obligacion(vencimiento=HOY)
        self.crear_regla_email(obligacion, 0)
        procesar(hoy=HOY)

        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)


class AplicarReglasConCorreoTests(BaseCorreo):
    """La decisión de si se crea o no la regla de EMAIL depende de la
    preferencia de la cuenta (perfil → Notificaciones por correo), no de
    un campo nuevo en el formulario de obligación."""

    def test_usuario_sin_correo_activado_no_crea_regla_de_email(self):
        from apps.obligaciones.forms import ObligacionForm

        self.client = self.client
        datos = self._datos_formulario()
        formulario = ObligacionForm(data=datos, usuario=self.usuario)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        obligacion = formulario.save()

        self.assertFalse(
            obligacion.reglas_recordatorio.filter(
                canal=CanalNotificacion.EMAIL, activa=True
            ).exists()
        )
        self.assertTrue(
            obligacion.reglas_recordatorio.filter(
                canal=CanalNotificacion.APP, activa=True
            ).exists()
        )

    def test_usuario_con_correo_activado_crea_ambos_canales(self):
        from apps.obligaciones.forms import ObligacionForm

        self.activar_correo()
        datos = self._datos_formulario()
        formulario = ObligacionForm(data=datos, usuario=self.usuario)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        obligacion = formulario.save()

        for canal in (CanalNotificacion.APP, CanalNotificacion.EMAIL):
            with self.subTest(canal=canal):
                activas = obligacion.reglas_recordatorio.filter(canal=canal, activa=True)
                self.assertEqual(set(activas.values_list("dias_antes", flat=True)), {1, 0})

    def _datos_formulario(self):
        return {
            "concepto": "Internet", "monto": "120000",
            "fecha_vencimiento": (HOY + timedelta(days=1)).isoformat(),
            "categoria": self.categoria.pk, "prioridad_usuario": "MEDIA",
            "descripcion": "", "enlace_pago": "", "proveedor": "", "referencia": "",
            "recordatorios": ["1", "0"],
        }


class FormularioObligacionCorreoTests(BaseCorreo):
    """A través del cliente de pruebas: lo más parecido a usar la app."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def _datos(self, **overrides):
        base = {
            "concepto": "Spotify", "monto": "20000",
            "fecha_vencimiento": (HOY + timedelta(days=1)).isoformat(),
            "categoria": self.categoria.pk, "prioridad_usuario": "MEDIA",
            "descripcion": "", "enlace_pago": "", "proveedor": "", "referencia": "",
            "recordatorios": ["1"],
        }
        base.update(overrides)
        return base

    def test_crear_con_correo_activado_genera_la_regla_de_email(self):
        self.activar_correo()

        respuesta = self.client.post(reverse("obligaciones:crear"), self._datos())

        self.assertEqual(respuesta.status_code, 302)
        obligacion = Obligacion.objects.get(concepto="Spotify")
        self.assertTrue(
            obligacion.reglas_recordatorio.filter(
                canal=CanalNotificacion.EMAIL, dias_antes=1, activa=True
            ).exists()
        )

    def test_editar_sin_cambiar_recordatorios_los_conserva(self):
        self.activar_correo()
        self.client.post(reverse("obligaciones:crear"), self._datos())
        obligacion = Obligacion.objects.get(concepto="Spotify")

        # Se reenvía el mismo formulario (como si solo se hubiera abierto y
        # guardado de nuevo sin tocar nada), cambiando solo la descripción.
        respuesta = self.client.post(
            reverse("obligaciones:editar", args=[obligacion.pk]),
            self._datos(descripcion="Actualizado"),
        )

        self.assertEqual(respuesta.status_code, 302)
        obligacion.refresh_from_db()
        self.assertEqual(obligacion.descripcion, "Actualizado")
        for canal in (CanalNotificacion.APP, CanalNotificacion.EMAIL):
            with self.subTest(canal=canal):
                self.assertTrue(
                    obligacion.reglas_recordatorio.filter(
                        canal=canal, dias_antes=1, activa=True
                    ).exists()
                )

    def test_apagar_el_correo_en_el_perfil_detiene_los_nuevos_avisos(self):
        """El cambio aplica a partir de la próxima vez que se guarda la
        obligación (crear o editar) — no reescribe reglas de obligaciones
        que no se toquen, como pide la Fase 2.A."""
        self.activar_correo()
        self.client.post(reverse("obligaciones:crear"), self._datos())
        obligacion = Obligacion.objects.get(concepto="Spotify")
        self.assertTrue(
            obligacion.reglas_recordatorio.filter(
                canal=CanalNotificacion.EMAIL, activa=True
            ).exists()
        )

        self.usuario.configuracion.notificaciones_email = False
        self.usuario.configuracion.save(update_fields=["notificaciones_email"])

        self.client.post(
            reverse("obligaciones:editar", args=[obligacion.pk]), self._datos()
        )

        obligacion.refresh_from_db()
        self.assertFalse(
            obligacion.reglas_recordatorio.filter(
                canal=CanalNotificacion.EMAIL, activa=True
            ).exists()
        )


class TareaDiariaEndpointTests(BaseCorreo):
    """El reemplazo sin costo del WebJob que Azure F1 no admite."""

    @override_settings(TAREA_DIARIA_TOKEN="")
    def test_sin_token_configurado_responde_503(self):
        respuesta = self.client.post(reverse("recordatorios:tarea_diaria"))
        self.assertEqual(respuesta.status_code, 503)

    @override_settings(TAREA_DIARIA_TOKEN="secreto-de-prueba")
    def test_token_incorrecto_responde_403(self):
        respuesta = self.client.post(
            reverse("recordatorios:tarea_diaria"),
            HTTP_X_TAREA_TOKEN="otro-valor",
        )
        self.assertEqual(respuesta.status_code, 403)

    @override_settings(TAREA_DIARIA_TOKEN="secreto-de-prueba")
    def test_sin_encabezado_responde_403(self):
        respuesta = self.client.post(reverse("recordatorios:tarea_diaria"))
        self.assertEqual(respuesta.status_code, 403)

    @override_settings(TAREA_DIARIA_TOKEN="secreto-de-prueba")
    def test_get_no_esta_permitido(self):
        respuesta = self.client.get(
            reverse("recordatorios:tarea_diaria"),
            HTTP_X_TAREA_TOKEN="secreto-de-prueba",
        )
        self.assertEqual(respuesta.status_code, 405)

    @override_settings(TAREA_DIARIA_TOKEN="secreto-de-prueba")
    def test_token_correcto_procesa_a_todos_los_usuarios(self):
        otro = Usuario.objects.create_user(
            email="otro@example.com", nombre="Otro", password="ClaveSegura123"
        )
        mia = self.crear_obligacion(concepto="Mía", vencimiento=timezone.localdate())
        suya = self.crear_obligacion(
            concepto="Suya", usuario=otro, vencimiento=timezone.localdate()
        )
        self.crear_regla_email(mia, 0)
        ConfiguracionRecordatorio.objects.create(
            obligacion=suya, dias_antes=0, canal=CanalNotificacion.APP
        )

        respuesta = self.client.post(
            reverse("recordatorios:tarea_diaria"),
            HTTP_X_TAREA_TOKEN="secreto-de-prueba",
        )

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["enviados"], 2)
        self.assertEqual(len(mail.outbox), 1)  # solo la de "mia" era EMAIL

    @override_settings(TAREA_DIARIA_TOKEN="secreto-de-prueba")
    def test_es_idempotente(self):
        obligacion = self.crear_obligacion(vencimiento=timezone.localdate())
        self.crear_regla_email(obligacion, 0)
        encabezado = {"HTTP_X_TAREA_TOKEN": "secreto-de-prueba"}

        self.client.post(reverse("recordatorios:tarea_diaria"), **encabezado)
        self.client.post(reverse("recordatorios:tarea_diaria"), **encabezado)

        self.assertEqual(Recordatorio.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)


class ComandoCorreoDePruebaTests(TestCase):
    """`enviar_correo_prueba`: no crea ninguna obligación ni recordatorio."""

    def test_envia_un_solo_correo_al_destino_pedido(self):
        from io import StringIO

        call_command("enviar_correo_prueba", "destino@example.com", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["destino@example.com"])
        self.assertEqual(Recordatorio.objects.count(), 0)
        self.assertEqual(Obligacion.objects.count(), 0)

    def test_un_rechazo_del_proveedor_da_un_error_claro_sin_marcar_nada(self):
        from io import StringIO

        from django.core.management.base import CommandError

        with patch(
            "apps.recordatorios.management.commands.enviar_correo_prueba.send_mail",
            side_effect=Exception("535 Authentication failed"),
        ):
            with self.assertRaises(CommandError) as contexto:
                call_command("enviar_correo_prueba", "destino@example.com", stdout=StringIO())

        self.assertIn("535 Authentication failed", str(contexto.exception))
        self.assertEqual(len(mail.outbox), 0)


class SistemaChecksCorreoTests(TestCase):
    """`manage.py check` debe avisar si producción quedó con el backend
    de consola — para que no se descubra el día de la sustentación."""

    def test_advierte_si_produccion_usa_el_backend_de_consola(self):
        from apps.core.checks import revisar_backend_correo

        with override_settings(
            DEBUG=False,
            EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        ):
            problemas = revisar_backend_correo(None)

        self.assertEqual(len(problemas), 1)
        self.assertEqual(problemas[0].id, "core.W001")

    def test_no_advierte_en_desarrollo(self):
        from apps.core.checks import revisar_backend_correo

        with override_settings(
            DEBUG=True,
            EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        ):
            problemas = revisar_backend_correo(None)

        self.assertEqual(problemas, [])

    def test_no_advierte_con_smtp_configurado(self):
        from apps.core.checks import revisar_backend_correo

        with override_settings(
            DEBUG=False,
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        ):
            problemas = revisar_backend_correo(None)

        self.assertEqual(problemas, [])
