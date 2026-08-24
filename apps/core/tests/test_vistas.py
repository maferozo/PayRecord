from django.test import SimpleTestCase
from django.urls import reverse


class InicioTests(SimpleTestCase):
    """La página pública debe renderizar sin tocar la base de datos."""

    def test_inicio_responde_200(self):
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertEqual(respuesta.status_code, 200)

    def test_inicio_usa_la_plantilla_base(self):
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertTemplateUsed(respuesta, "base.html")
        self.assertTemplateUsed(respuesta, "core/inicio.html")

    def test_inicio_aplica_el_filtro_de_moneda(self):
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertContains(respuesta, "$1.250.000")
