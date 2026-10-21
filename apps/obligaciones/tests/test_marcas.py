from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.obligaciones.services.marcas import detectar_marca


class DeteccionDeMarcaTests(SimpleTestCase):

    def test_reconoce_variaciones_de_mayusculas_y_minusculas(self):
        for texto in ("spotify", "SPOTIFY", "Spotify", "sPoTiFy"):
            with self.subTest(texto=texto):
                marca = detectar_marca(texto)
                self.assertIsNotNone(marca)
                self.assertEqual(marca.clave, "spotify")

    def test_reconoce_con_palabras_extra(self):
        marca = detectar_marca("Spotify Premium")
        self.assertEqual(marca.clave, "spotify")

    def test_reconoce_con_espacios_de_mas_alrededor(self):
        marca = detectar_marca("   Netflix   ")
        self.assertEqual(marca.clave, "netflix")

    def test_reconoce_marca_compuesta_con_espacios_variables(self):
        """Nombres de dos palabras ("Apple Music") deben tolerar más o
        menos espacio entre ellas, que es la variación real que escribe
        la gente -- no partir una palabra suelta por la mitad."""
        for texto in ("Apple  Music", "AppleMusic", "apple music"):
            with self.subTest(texto=texto):
                self.assertEqual(detectar_marca(texto).clave, "applemusic")

    def test_youtube_music_ya_no_se_ofrece_para_registros_nuevos(self):
        """Encargo final: se elimina como opción nueva -- un "YouTube
        Music" escrito hoy cae en el "YouTube Premium" genérico. La marca
        "youtubemusic" sigue existiendo en el registro (obtener_marca)
        solo para no perder el logo de lo ya guardado así."""
        from apps.obligaciones.services.marcas import obtener_marca

        marca = detectar_marca("YouTube Music")
        self.assertEqual(marca.clave, "youtube")

        self.assertEqual(obtener_marca("youtubemusic").nombre, "YouTube Music")

    def test_apple_music_no_se_queda_en_apple_generico(self):
        marca = detectar_marca("Apple Music")
        self.assertEqual(marca.clave, "applemusic")

    def test_google_one_no_se_queda_en_google_generico(self):
        marca = detectar_marca("Google One")
        self.assertEqual(marca.clave, "googleone")

    def test_netflix(self):
        self.assertEqual(detectar_marca("Netflix").clave, "netflix")

    def test_amazon_prime_no_se_queda_en_amazon_generico(self):
        marca = detectar_marca("Amazon Prime")
        self.assertEqual(marca.clave, "amazonprime")

    def test_marca_desconocida_no_reconoce_nada(self):
        """Respaldo: el llamador usa el icono de categoría (ver
        obligaciones_extras.badge_obligacion)."""
        for texto in ("Universidad", "Arriendo", "Cuota condominio"):
            with self.subTest(texto=texto):
                self.assertIsNone(detectar_marca(texto))

    def test_reconoce_obligaciones_sin_categoria_propia(self):
        """Gimnasio, transporte y seguros no tienen categoría dedicada en
        el catálogo del sistema (a diferencia de educación o créditos),
        así que sí se autodetectan para que queden identificables."""
        casos = {
            "Gimnasio Local": "gimnasio",
            "Suscripción al gym": "gimnasio",
            "Transporte público": "transporte",
            "Seguro de vida": "seguros",
            "Seguros Bolívar": "seguros",
        }
        for texto, clave_esperada in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(detectar_marca(texto).clave, clave_esperada)

    def test_epm_se_reconoce_por_nombre_propio(self):
        self.assertEqual(detectar_marca("EPM").clave, "epm")
        self.assertEqual(detectar_marca("Factura EPM de octubre").clave, "epm")

    def test_epm_se_reconoce_por_frases_genericas_de_servicios_del_hogar(self):
        """Encargo final §1: "Pagar servicios del hogar/públicos/de la
        casa" debe mostrar el logo de EPM automáticamente, sin preguntar
        nada."""
        for texto in (
            "Pagar servicios del hogar", "Pagar servicios públicos",
            "Pago de servicios de la casa", "servicios del hogar",
        ):
            with self.subTest(texto=texto):
                self.assertEqual(detectar_marca(texto).clave, "epm")

    def test_vanti_agua_energia_gas_ya_no_son_marcas_propias(self):
        """§1: se simplificó el selector -- esos ya no son marcas
        independientes. Un nombre que las mencione y no encaje con EPM
        cae al icono genérico de la categoría (no se le asigna EPM por
        error, que sería una marca incorrecta)."""
        for texto in ("Factura Vanti", "Agua y acueducto", "Recibo de energía", "Gas natural"):
            with self.subTest(texto=texto):
                self.assertIsNone(detectar_marca(texto))

    def test_proveedores_locales_de_telecom_no_se_autodetectan(self):
        """A propósito: "Claro" se confunde demasiado fácil con la palabra
        común, y en general los proveedores locales solo deben asignarse
        a mano (Obligacion.marca), nunca por adivinanza del texto."""
        for texto in ("Claro", "Internet Claro", "Tigo", "Plan WOM", "ETB hogar", "Movistar"):
            with self.subTest(texto=texto):
                self.assertIsNone(detectar_marca(texto))

    def test_google_drive_se_reconoce_y_no_se_queda_en_google_generico(self):
        self.assertEqual(detectar_marca("Google Drive").clave, "googledrive")

    def test_no_confunde_nombres_similares(self):
        """"Applebee's" no es Apple; ningún nombre parecido debe disparar
        una marca por simple coincidencia parcial de letras."""
        self.assertIsNone(detectar_marca("Restaurante Applebees"))

    def test_cadena_vacia_no_lanza_error(self):
        self.assertIsNone(detectar_marca(""))
        self.assertIsNone(detectar_marca(None))


class OpcionesOperadorTests(SimpleTestCase):
    """La pregunta "¿Qué operador tienes?" del formulario -- encargo
    final §2: exactamente estas 5 opciones, ni una más."""

    def test_son_exactamente_las_5_opciones_pedidas(self):
        from apps.obligaciones.services.marcas import opciones_operador

        nombres = [nombre for _clave, nombre in opciones_operador()]
        self.assertEqual(
            nombres, ["Claro", "Movistar", "Tigo", "WOM", "Otro proveedor"]
        )

    def test_etb_ya_no_esta_entre_las_opciones(self):
        from apps.obligaciones.services.marcas import opciones_operador

        claves = [clave for clave, _nombre in opciones_operador()]
        self.assertNotIn("etb", claves)


class ArchivosDeLogoTests(SimpleTestCase):
    """Que cada logo "svg" del registro realmente exista en disco: si
    alguien borra o renombra un archivo, esto falla en CI en vez de
    descubrirse con una tarjeta rota en producción."""

    def test_cada_logo_svg_del_registro_existe(self):
        from apps.obligaciones.services.marcas import _REGISTRO

        raiz_estaticos = Path(settings.BASE_DIR) / "static"
        for marca in _REGISTRO:
            if marca.tipo != "svg":
                continue
            with self.subTest(marca=marca.clave):
                ruta = raiz_estaticos / marca.valor
                self.assertTrue(ruta.is_file(), f"No existe {ruta}")
