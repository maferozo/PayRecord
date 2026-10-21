from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.obligaciones.models import Categoria, Obligacion
from apps.usuarios.models import Empresa, TipoUsuario

Usuario = get_user_model()


def crear_personal(email="maria@example.com"):
    return Usuario.objects.create_user(email=email, nombre="María", password="ClaveSegura123")


def crear_empresa(email="empresa@example.com", nombre_empresa="Comercial XYZ"):
    return Usuario.objects.create_user(
        email=email,
        nombre="Gerente",
        password="ClaveSegura123",
        tipo_usuario=TipoUsuario.EMPRESA,
        empresa=Empresa.objects.create(nombre=nombre_empresa),
    )


class BaseObligaciones(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_categorias", verbosity=0)
        cls.categoria = Categoria.objects.get(codigo="servicios")

    def datos_validos(self, **extra):
        datos = {
            "concepto": "Internet",
            "monto": "120000",
            "fecha_vencimiento": (timezone.localdate() + timedelta(days=5)).isoformat(),
            "categoria": self.categoria.pk,
            "prioridad_usuario": "MEDIA",
            "descripcion": "",
            "enlace_pago": "",
        }
        datos.update(extra)
        return datos


class CrearObligacionTests(BaseObligaciones):
    """§36: creación correcta, valor inválido, fecha inválida."""

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)

    def test_creacion_correcta(self):
        respuesta = self.client.post(reverse("obligaciones:crear"), self.datos_validos())

        obligacion = Obligacion.objects.get(concepto="Internet")
        self.assertRedirects(respuesta, reverse("obligaciones:detalle", args=[obligacion.pk]))
        self.assertEqual(obligacion.usuario, self.usuario)
        self.assertEqual(obligacion.monto, Decimal("120000.00"))
        self.assertFalse(obligacion.pagada)
        self.assertIsNone(obligacion.empresa)

    def test_monto_negativo_es_rechazado(self):
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos_validos(monto="-5000")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())

    def test_monto_cero_es_rechazado(self):
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos_validos(monto="0")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())

    def test_monto_no_numerico_es_rechazado(self):
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos_validos(monto="mucho dinero")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())

    def test_fecha_invalida_es_rechazada(self):
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos_validos(fecha_vencimiento="31/02/2026")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())

    def test_fecha_pasada_se_admite(self):
        """Registrar una deuda ya vencida es un caso de uso legítimo."""
        fecha = (timezone.localdate() - timedelta(days=30)).isoformat()
        self.client.post(reverse("obligaciones:crear"), self.datos_validos(fecha_vencimiento=fecha))
        self.assertTrue(Obligacion.objects.get(concepto="Internet").esta_vencida)

    def test_enlace_de_pago_invalido_es_rechazado(self):
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos_validos(enlace_pago="no-es-una-url")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())

    def test_concepto_vacio_es_rechazado(self):
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos_validos(concepto="")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())

    def test_no_puede_usar_una_categoria_de_otro_ambito(self):
        """Un usuario personal no puede asignar una categoría de empresa."""
        nomina = Categoria.objects.get(codigo="nomina")
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos_validos(categoria=nomina.pk)
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())

    def test_no_puede_usar_la_categoria_privada_de_otro_usuario(self):
        otro = crear_personal("otro@example.com")
        categoria_ajena = Categoria.objects.create(
            nombre="Gimnasio", usuario=otro, ambito="PERSONAL"
        )
        respuesta = self.client.post(
            reverse("obligaciones:crear"), self.datos_validos(categoria=categoria_ajena.pk)
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Obligacion.objects.exists())


class ObligacionEmpresaTests(BaseObligaciones):

    def setUp(self):
        self.usuario = crear_empresa()
        self.client.force_login(self.usuario)

    def test_la_empresa_se_asigna_sola(self):
        self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(proveedor="Proveedor XYZ", referencia="FAC-001"),
        )
        obligacion = Obligacion.objects.get(concepto="Internet")
        self.assertEqual(obligacion.empresa, self.usuario.empresa)
        self.assertEqual(obligacion.proveedor, "Proveedor XYZ")

    def test_el_usuario_personal_no_ve_los_campos_empresariales(self):
        self.client.logout()
        self.client.force_login(crear_personal())
        respuesta = self.client.get(reverse("obligaciones:crear"))
        self.assertNotIn("proveedor", respuesta.context["form"].fields)

    def test_el_usuario_empresa_si_los_ve(self):
        respuesta = self.client.get(reverse("obligaciones:crear"))
        self.assertIn("proveedor", respuesta.context["form"].fields)


class EditarYEliminarTests(BaseObligaciones):

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)
        self.obligacion = Obligacion.objects.create(
            usuario=self.usuario,
            concepto="Internet",
            monto=120000,
            fecha_vencimiento=timezone.localdate() + timedelta(days=5),
            categoria=self.categoria,
        )

    def test_editar(self):
        self.client.post(
            reverse("obligaciones:editar", args=[self.obligacion.pk]),
            self.datos_validos(concepto="Internet fibra", monto="135000"),
        )
        self.obligacion.refresh_from_db()
        self.assertEqual(self.obligacion.concepto, "Internet fibra")
        self.assertEqual(self.obligacion.monto, Decimal("135000.00"))

    def test_eliminar_es_logico(self):
        """La fila se conserva para no romper el historial (decisión D7)."""
        respuesta = self.client.post(reverse("obligaciones:eliminar", args=[self.obligacion.pk]))
        self.assertRedirects(respuesta, reverse("obligaciones:lista"))

        self.obligacion.refresh_from_db()
        self.assertIsNotNone(self.obligacion.eliminada_en)
        self.assertTrue(Obligacion.objects.filter(pk=self.obligacion.pk).exists())
        self.assertNotIn(
            self.obligacion, Obligacion.objects.visibles_para(self.usuario)
        )


class MarcarPagadaTests(BaseObligaciones):
    """§32 punto 8 y §36."""

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)
        self.obligacion = Obligacion.objects.create(
            usuario=self.usuario,
            concepto="Internet",
            monto=120000,
            fecha_vencimiento=timezone.localdate() + timedelta(days=5),
            categoria=self.categoria,
        )

    def test_marcar_pagada(self):
        self.client.post(reverse("obligaciones:cambiar_pago", args=[self.obligacion.pk]))
        self.obligacion.refresh_from_db()

        self.assertTrue(self.obligacion.pagada)
        self.assertEqual(self.obligacion.fecha_pago, timezone.localdate())
        self.assertEqual(self.obligacion.estado_actual, "PAGADA")

    def test_volver_a_pendiente(self):
        self.obligacion.marcar_pagada()
        self.client.post(reverse("obligaciones:cambiar_pago", args=[self.obligacion.pk]))
        self.obligacion.refresh_from_db()

        self.assertFalse(self.obligacion.pagada)
        self.assertIsNone(self.obligacion.fecha_pago)

    def test_no_se_puede_marcar_por_get(self):
        """Cambiar datos con GET permitiría hacerlo desde un enlace."""
        respuesta = self.client.get(
            reverse("obligaciones:cambiar_pago", args=[self.obligacion.pk])
        )
        self.assertEqual(respuesta.status_code, 405)
        self.obligacion.refresh_from_db()
        self.assertFalse(self.obligacion.pagada)


class AislamientoEntreUsuariosTests(BaseObligaciones):
    """§28 y §36: el usuario A nunca alcanza los datos del usuario B."""

    def setUp(self):
        self.ana = crear_personal("ana@example.com")
        self.beto = crear_personal("beto@example.com")
        self.obligacion_de_ana = Obligacion.objects.create(
            usuario=self.ana,
            concepto="Crédito de Ana",
            monto=450000,
            fecha_vencimiento=timezone.localdate() + timedelta(days=3),
            categoria=self.categoria,
        )
        self.client.force_login(self.beto)

    def test_no_aparece_en_el_listado(self):
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertNotContains(respuesta, "Crédito de Ana")

    def test_no_puede_verla(self):
        respuesta = self.client.get(
            reverse("obligaciones:detalle", args=[self.obligacion_de_ana.pk])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_editarla(self):
        respuesta = self.client.get(
            reverse("obligaciones:editar", args=[self.obligacion_de_ana.pk])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_modificarla_por_post(self):
        self.client.post(
            reverse("obligaciones:editar", args=[self.obligacion_de_ana.pk]),
            self.datos_validos(concepto="Secuestrada"),
        )
        self.obligacion_de_ana.refresh_from_db()
        self.assertEqual(self.obligacion_de_ana.concepto, "Crédito de Ana")

    def test_no_puede_eliminarla(self):
        respuesta = self.client.post(
            reverse("obligaciones:eliminar", args=[self.obligacion_de_ana.pk])
        )
        self.assertEqual(respuesta.status_code, 404)
        self.obligacion_de_ana.refresh_from_db()
        self.assertIsNone(self.obligacion_de_ana.eliminada_en)

    def test_no_puede_marcarla_como_pagada(self):
        respuesta = self.client.post(
            reverse("obligaciones:cambiar_pago", args=[self.obligacion_de_ana.pk])
        )
        self.assertEqual(respuesta.status_code, 404)
        self.obligacion_de_ana.refresh_from_db()
        self.assertFalse(self.obligacion_de_ana.pagada)

    def test_ana_si_accede_a_la_suya(self):
        self.client.logout()
        self.client.force_login(self.ana)
        respuesta = self.client.get(
            reverse("obligaciones:detalle", args=[self.obligacion_de_ana.pk])
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_todas_las_rutas_exigen_sesion(self):
        self.client.logout()
        rutas = [
            reverse("obligaciones:lista"),
            reverse("obligaciones:crear"),
            reverse("obligaciones:detalle", args=[self.obligacion_de_ana.pk]),
            reverse("obligaciones:editar", args=[self.obligacion_de_ana.pk]),
            reverse("obligaciones:eliminar", args=[self.obligacion_de_ana.pk]),
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/cuenta/entrar/", respuesta.url)


class VisibilidadEmpresarialTests(BaseObligaciones):
    """§26: la arquitectura debe admitir varios usuarios por empresa."""

    def test_dos_usuarios_de_la_misma_empresa_comparten_obligaciones(self):
        empresa = Empresa.objects.create(nombre="Comercial XYZ")
        gerente = Usuario.objects.create_user(
            email="gerente@xyz.com", nombre="Gerente", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=empresa,
        )
        contador = Usuario.objects.create_user(
            email="contador@xyz.com", nombre="Contador", password="ClaveSegura123",
            tipo_usuario=TipoUsuario.EMPRESA, empresa=empresa,
        )
        obligacion = Obligacion.objects.create(
            usuario=gerente, empresa=empresa, concepto="Proveedor XYZ", monto=850000,
            fecha_vencimiento=timezone.localdate() + timedelta(days=5), categoria=self.categoria,
        )

        self.assertIn(obligacion, Obligacion.objects.visibles_para(contador))

    def test_una_empresa_no_ve_las_obligaciones_de_otra(self):
        usuario_a = crear_empresa("a@xyz.com", "Empresa A")
        usuario_b = crear_empresa("b@abc.com", "Empresa B")
        obligacion_a = Obligacion.objects.create(
            usuario=usuario_a, empresa=usuario_a.empresa, concepto="Nómina A", monto=1200000,
            fecha_vencimiento=timezone.localdate() + timedelta(days=5), categoria=self.categoria,
        )

        self.assertNotIn(obligacion_a, Obligacion.objects.visibles_para(usuario_b))


class FiltrosListadoTests(BaseObligaciones):

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)
        hoy = timezone.localdate()
        self.vencida = Obligacion.objects.create(
            usuario=self.usuario, concepto="Arriendo", monto=900000,
            fecha_vencimiento=hoy - timedelta(days=5), categoria=self.categoria,
        )
        self.futura = Obligacion.objects.create(
            usuario=self.usuario, concepto="Netflix", monto=35900,
            fecha_vencimiento=hoy + timedelta(days=40), categoria=self.categoria,
        )

    def test_filtrar_por_estado(self):
        respuesta = self.client.get(reverse("obligaciones:lista"), {"estado": "VENCIDA"})
        self.assertContains(respuesta, "Arriendo")
        self.assertNotContains(respuesta, "Netflix")

    def test_buscar_por_texto(self):
        respuesta = self.client.get(reverse("obligaciones:lista"), {"q": "netfl"})
        self.assertContains(respuesta, "Netflix")
        self.assertNotContains(respuesta, "Arriendo")

    def test_total_pendiente_suma_solo_lo_no_pagado(self):
        self.futura.marcar_pagada()
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertEqual(respuesta.context["total_pendiente"], Decimal("900000.00"))


class SeleccionManualDeMarcaTests(BaseObligaciones):
    """§D del encargo: elegir la marca a mano desde el formulario, y que
    quede guardada de forma consistente (la clave, no el texto)."""

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)

    def test_elegir_claro_desde_el_selector_lo_guarda(self):
        """"Claro" no se autodetecta del texto (es ambiguo): la única
        forma de asignarlo es este selector."""
        self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Plan celular", marca="claro"),
        )

        obligacion = Obligacion.objects.get(concepto="Plan celular")
        self.assertEqual(obligacion.marca, "claro")

    def test_dejar_en_automatico_no_guarda_nada_en_el_campo(self):
        self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Spotify Premium"),  # sin "marca"
        )

        obligacion = Obligacion.objects.get(concepto="Spotify Premium")
        self.assertEqual(obligacion.marca, "")

    def test_no_es_obligatorio_elegir_proveedor(self):
        """Un texto que ni se autodetecta ni se elige a mano no debe
        impedir guardar la obligación."""
        respuesta = self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Cuota administración"),
        )
        self.assertEqual(Obligacion.objects.filter(concepto="Cuota administración").count(), 1)
        self.assertEqual(respuesta.status_code, 302)

    def test_una_clave_que_no_existe_en_el_registro_es_invalida(self):
        """El campo es un ChoiceField contra el registro real: no se puede
        guardar cualquier texto arbitrario (eso es justo "depender del
        texto visible", lo que se pidió evitar)."""
        formulario = self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Algo", marca="marca-inventada"),
        )
        self.assertEqual(formulario.status_code, 200)  # se queda en el formulario
        self.assertFalse(Obligacion.objects.filter(concepto="Algo").exists())

    def test_editar_conserva_la_marca_elegida(self):
        self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Internet hogar", marca="movistar"),
        )
        obligacion = Obligacion.objects.get(concepto="Internet hogar")

        self.client.post(
            reverse("obligaciones:editar", args=[obligacion.pk]),
            self.datos_validos(concepto="Internet hogar", marca="movistar", descripcion="actualizado"),
        )

        obligacion.refresh_from_db()
        self.assertEqual(obligacion.marca, "movistar")
        self.assertEqual(obligacion.descripcion, "actualizado")

    def test_la_eleccion_manual_gana_sobre_la_deteccion_automatica(self):
        """Un concepto que diría "internet" por el texto, pero con un
        operador elegido a mano -- esa elección manda sobre lo que el
        texto hubiera sugerido."""
        from apps.obligaciones.templatetags.obligaciones_extras import badge_obligacion

        self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Internet del hogar", marca="movistar"),
        )
        obligacion = Obligacion.objects.get(concepto="Internet del hogar")

        contexto = badge_obligacion(obligacion)

        self.assertEqual(contexto["nombre_accesible"], "Movistar")

    def test_una_clave_fuera_de_las_5_opciones_de_operador_es_invalida(self):
        """El campo ya no acepta cualquier clave del registro (p. ej.
        "netflix"): desde el encargo final, solo los 5 operadores de
        celular/internet se eligen a mano vía formulario."""
        respuesta = self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Algo", marca="netflix"),
        )
        self.assertEqual(respuesta.status_code, 200)  # se queda en el formulario
        self.assertFalse(Obligacion.objects.filter(concepto="Algo").exists())


class BadgeDeObligacionEnLasVistasTests(BaseObligaciones):
    """El logo aparece en las 3 pantallas pedidas explícitamente."""

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)
        self.obligacion = Obligacion.objects.create(
            usuario=self.usuario, concepto="Spotify", monto=Decimal("20000"),
            fecha_vencimiento=timezone.localdate() + timedelta(days=5),
            categoria=self.categoria,
        )

    def test_aparece_en_la_lista(self):
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertContains(respuesta, 'title="Spotify"')
        self.assertContains(respuesta, "<svg")  # el logo real, no el icono de respaldo

    def test_aparece_en_el_detalle(self):
        respuesta = self.client.get(reverse("obligaciones:detalle", args=[self.obligacion.pk]))
        self.assertContains(respuesta, 'title="Spotify"')

    def test_aparece_en_el_dashboard(self):
        respuesta = self.client.get(reverse("dashboard:inicio"))
        self.assertContains(respuesta, 'title="Spotify"')

    def test_una_obligacion_sin_marca_reconocida_usa_el_icono_de_categoria(self):
        Obligacion.objects.create(
            usuario=self.usuario, concepto="Universidad", monto=Decimal("500000"),
            fecha_vencimiento=timezone.localdate() + timedelta(days=5),
            categoria=self.categoria,
        )
        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertContains(respuesta, f'title="{self.categoria.nombre}"')


class EpmAutomaticoTests(BaseObligaciones):
    """Encargo final §1: EPM se reconoce solo, sin preguntar nada."""

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)

    def test_registrar_servicios_del_hogar_muestra_epm_sin_preguntar(self):
        respuesta = self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Pagar servicios del hogar"),
        )
        self.assertEqual(respuesta.status_code, 302)  # no se quedó esperando un campo extra

        obligacion = Obligacion.objects.get(concepto="Pagar servicios del hogar")
        self.assertEqual(obligacion.marca, "")  # nada guardado a mano: fue automático

        lista = self.client.get(reverse("obligaciones:lista"))
        self.assertContains(lista, 'title="EPM"')

    def test_un_servicio_del_hogar_no_cubierto_usa_icono_generico(self):
        """"Gas natural" ya no es EPM (se simplificó el selector): debe
        caer al icono de categoría, no asignarse una marca incorrecta."""
        self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Gas natural"),
        )
        obligacion = Obligacion.objects.get(concepto="Gas natural")

        respuesta = self.client.get(reverse("obligaciones:lista"))
        self.assertNotContains(respuesta, 'title="EPM"')
        self.assertContains(respuesta, f'title="{obligacion.categoria.nombre}"')


class PreguntaDeOperadorEnElFormularioTests(BaseObligaciones):
    """Encargo final §2: la estructura HTML que el JS de la plantilla usa
    para mostrar/ocultar la pregunta -- lo que el JS hace en el navegador
    (mostrar/ocultar según lo que se escriba) se verificó manualmente en
    vivo, Django no ejecuta JavaScript en estas pruebas."""

    def setUp(self):
        self.usuario = crear_personal()
        self.client.force_login(self.usuario)

    def test_el_grupo_de_operador_existe_y_empieza_oculto(self):
        respuesta = self.client.get(reverse("obligaciones:crear"))
        self.assertContains(respuesta, 'id="grupo-operador"')
        self.assertContains(respuesta, 'id="id_operador"')
        # El atributo "hidden" debe estar en el HTML inicial -- el JS lo
        # quita si corresponde, pero el estado de reposo es oculto.
        html = respuesta.content.decode()
        indice = html.find('id="grupo-operador"')
        self.assertIn("hidden", html[max(0, indice - 20):indice + 120])

    def test_las_opciones_del_select_son_las_5_del_operador(self):
        respuesta = self.client.get(reverse("obligaciones:crear"))
        for nombre in ("Claro", "Movistar", "Tigo", "WOM", "Otro proveedor"):
            with self.subTest(nombre=nombre):
                self.assertContains(respuesta, f">{nombre}<")
        self.assertNotContains(respuesta, ">ETB<")

    def test_elegir_un_operador_sin_relacion_con_el_texto_igual_se_guarda(self):
        """El JS decide cuándo mostrar la pregunta, pero el valor que
        llegue al backend se guarda igual -- la validación no depende de
        si el texto "parece" de celular."""
        self.client.post(
            reverse("obligaciones:crear"),
            self.datos_validos(concepto="Mi plan de datos", marca="tigo"),
        )
        obligacion = Obligacion.objects.get(concepto="Mi plan de datos")
        self.assertEqual(obligacion.marca, "tigo")
