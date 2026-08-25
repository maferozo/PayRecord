"""Filtros de plantilla y comando de datos de prueba."""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from apps.obligaciones.enums import EstadoObligacion, Prioridad
from apps.obligaciones.models import Categoria, Obligacion
from apps.obligaciones.templatetags import obligaciones_extras as extras

Usuario = get_user_model()


class FiltrosEstadoTests(SimpleTestCase):

    def test_etiqueta_de_cada_estado(self):
        esperado = {
            "PENDIENTE": "Pendiente",
            "PROXIMA_VENCER": "Próxima a vencer",
            "VENCIDA": "Vencida",
            "PAGADA": "Pagada",
        }
        for valor, etiqueta in esperado.items():
            with self.subTest(valor=valor):
                self.assertEqual(extras.etiqueta_estado(valor), etiqueta)

    def test_clase_css_de_cada_estado(self):
        self.assertEqual(extras.clase_estado("VENCIDA"), "pr-estado-vencida")
        self.assertEqual(extras.clase_estado("PROXIMA_VENCER"), "pr-estado-proxima_vencer")

    def test_icono_de_cada_estado(self):
        self.assertEqual(extras.icono_estado("PAGADA"), "bi-check-circle")
        self.assertEqual(extras.icono_estado("VENCIDA"), "bi-x-circle")

    def test_un_valor_desconocido_no_rompe_la_plantilla(self):
        """Un dato inesperado debe degradar, no reventar la página."""
        self.assertEqual(extras.etiqueta_estado("INVENTADO"), "INVENTADO")
        self.assertEqual(extras.icono_estado("INVENTADO"), "bi-circle")
        self.assertEqual(extras.clase_estado(""), "pr-estado-pendiente")
        self.assertEqual(extras.etiqueta_estado(None), "")

    def test_filtros_de_prioridad(self):
        self.assertEqual(extras.etiqueta_prioridad("ALTA"), "Alta")
        self.assertEqual(extras.clase_prioridad("ALTA"), "pr-prioridad-alta")
        self.assertEqual(extras.clase_prioridad(""), "")
        self.assertEqual(extras.etiqueta_prioridad("INVENTADA"), "INVENTADA")

    def test_los_enums_exponen_su_clase_css(self):
        self.assertEqual(EstadoObligacion.VENCIDA.clase_css, "pr-estado-vencida")
        self.assertEqual(Prioridad.ALTA.value, "ALTA")


class CargarDatosPruebaTests(TestCase):
    """§37: datos ficticios para desarrollo."""

    def test_exige_que_existan_las_categorias(self):
        with self.assertRaises(CommandError):
            call_command("cargar_datos_prueba", verbosity=0)

    def test_crea_las_dos_cuentas_y_sus_obligaciones(self):
        call_command("cargar_categorias", verbosity=0)
        call_command("cargar_datos_prueba", verbosity=0)

        maria = Usuario.objects.get(email="maria@example.com")
        gerente = Usuario.objects.get(email="gerente@comercialxyz.com")

        self.assertTrue(maria.es_personal)
        self.assertTrue(gerente.es_empresa)
        self.assertIsNotNone(gerente.empresa)
        self.assertEqual(Obligacion.objects.filter(usuario=maria).count(), 8)
        self.assertEqual(Obligacion.objects.filter(usuario=gerente).count(), 6)

    def test_las_contrasenas_quedan_utilizables(self):
        call_command("cargar_categorias", verbosity=0)
        call_command("cargar_datos_prueba", verbosity=0)

        maria = Usuario.objects.get(email="maria@example.com")
        self.assertTrue(maria.check_password("Demo12345"))

    def test_genera_los_cuatro_estados(self):
        call_command("cargar_categorias", verbosity=0)
        call_command("cargar_datos_prueba", verbosity=0)

        maria = Usuario.objects.get(email="maria@example.com")
        estados = set(
            Obligacion.objects.para_usuario(maria).values_list("estado", flat=True)
        )
        self.assertEqual(len(estados), 4)

    def test_configura_recordatorios(self):
        call_command("cargar_categorias", verbosity=0)
        call_command("cargar_datos_prueba", verbosity=0)

        sin_pagar = Obligacion.objects.filter(pagada=False)
        for obligacion in sin_pagar:
            with self.subTest(concepto=obligacion.concepto):
                self.assertTrue(obligacion.reglas_recordatorio.filter(activa=True).exists())

    def test_es_idempotente(self):
        call_command("cargar_categorias", verbosity=0)
        call_command("cargar_datos_prueba", verbosity=0)
        call_command("cargar_datos_prueba", verbosity=0)
        call_command("cargar_datos_prueba", verbosity=0)

        self.assertEqual(Usuario.objects.count(), 2)
        self.assertEqual(Obligacion.objects.count(), 14)

    def test_limpiar_rehace_las_obligaciones(self):
        call_command("cargar_categorias", verbosity=0)
        call_command("cargar_datos_prueba", verbosity=0)
        call_command("cargar_datos_prueba", limpiar=True, verbosity=0)

        self.assertEqual(Obligacion.objects.count(), 14)
        self.assertEqual(Usuario.objects.count(), 2)


class CargarCategoriasActualizarTests(TestCase):

    def test_actualizar_refresca_los_valores(self):
        call_command("cargar_categorias", verbosity=0)

        categoria = Categoria.objects.get(codigo="creditos")
        categoria.peso_prioridad = 0
        categoria.color = "#000000"
        categoria.save()

        call_command("cargar_categorias", actualizar=True, verbosity=0)

        categoria.refresh_from_db()
        self.assertEqual(categoria.peso_prioridad, 5)
        self.assertEqual(categoria.color, "#DC2626")

    def test_sin_actualizar_no_pisa_los_cambios(self):
        call_command("cargar_categorias", verbosity=0)

        categoria = Categoria.objects.get(codigo="creditos")
        categoria.peso_prioridad = 1
        categoria.save()

        call_command("cargar_categorias", verbosity=0)

        categoria.refresh_from_db()
        self.assertEqual(categoria.peso_prioridad, 1)


class MixinPropiedadTests(TestCase):
    """El mixin avisa si un modelo no implementa `visibles_para`."""

    def test_exige_el_manager_adecuado(self):
        from apps.core.mixins import PropiedadDelUsuarioMixin

        class VistaMal(PropiedadDelUsuarioMixin):
            model = Categoria  # su manager no tiene visibles_para

            class request:  # noqa: N801
                user = None

        with self.assertRaises(NotImplementedError):
            VistaMal().get_queryset()

    def test_funciona_con_un_modelo_que_si_lo_implementa(self):
        from apps.core.mixins import PropiedadDelUsuarioMixin

        usuario = Usuario.objects.create_user(
            email="maria@example.com", nombre="María", password="ClaveSegura123"
        )

        class VistaBien(PropiedadDelUsuarioMixin):
            model = Obligacion

        vista = VistaBien()
        vista.request = type("Peticion", (), {"user": usuario})()

        self.assertEqual(list(vista.get_queryset()), [])
