from django import forms

from .enums import AmbitoCategoria
from .models import Categoria

# Paleta acotada: mantiene la coherencia visual de §22 y evita que el
# usuario elija colores ilegibles sobre fondo claro.
COLORES = [
    ("#2563EB", "Azul"),
    ("#0EA5E9", "Celeste"),
    ("#10B981", "Verde"),
    ("#F59E0B", "Ámbar"),
    ("#DC2626", "Rojo"),
    ("#7C3AED", "Morado"),
    ("#EC4899", "Rosa"),
    ("#6B7280", "Gris"),
]

ICONOS = [
    ("bi-tag", "Etiqueta"),
    ("bi-house-door", "Casa"),
    ("bi-lightning-charge", "Servicios"),
    ("bi-bank", "Banco"),
    ("bi-cart", "Compras"),
    ("bi-truck", "Proveedor"),
    ("bi-people", "Personas"),
    ("bi-heart-pulse", "Salud"),
    ("bi-mortarboard", "Educación"),
    ("bi-window-stack", "Software"),
    ("bi-file-earmark-text", "Documento"),
    ("bi-three-dots", "Otros"),
]


class CategoriaForm(forms.ModelForm):
    """Alta y edición de categorías propias del usuario.

    El ámbito no se pide: se deduce del tipo de cuenta, porque una categoría
    personalizada solo tiene sentido dentro del escenario de quien la crea.
    """

    color = forms.ChoiceField(label="Color", choices=COLORES, initial="#2563EB")
    icono = forms.ChoiceField(label="Icono", choices=ICONOS, initial="bi-tag")

    class Meta:
        model = Categoria
        fields = ("nombre", "color", "icono", "peso_prioridad")
        labels = {"peso_prioridad": "Importancia (0 a 5)"}
        help_texts = {
            "peso_prioridad": "Cuánto debe pesar esta categoría al ordenar tus "
                              "obligaciones por prioridad.",
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields["peso_prioridad"].widget = forms.NumberInput(
            attrs={"min": 0, "max": 5, "step": 1}
        )

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()

        duplicadas = Categoria.objects.filter(
            usuario=self.usuario, nombre__iexact=nombre
        ).exclude(pk=self.instance.pk)
        if duplicadas.exists():
            raise forms.ValidationError("Ya tienes una categoría con ese nombre.")

        # Tampoco debe chocar con una predeterminada visible para este usuario.
        ambito = (
            AmbitoCategoria.EMPRESA if self.usuario.es_empresa else AmbitoCategoria.PERSONAL
        )
        choca = Categoria.objects.predeterminadas().filter(
            nombre__iexact=nombre, ambito__in=[ambito, AmbitoCategoria.AMBOS]
        )
        if choca.exists():
            raise forms.ValidationError(
                "Ya existe una categoría del sistema con ese nombre. Elige otro."
            )
        return nombre

    def clean_peso_prioridad(self):
        peso = self.cleaned_data["peso_prioridad"]
        if peso > 5:
            raise forms.ValidationError("La importancia va de 0 a 5.")
        return peso

    def save(self, commit=True):
        categoria = super().save(commit=False)
        categoria.usuario = self.usuario
        categoria.codigo = None  # el código es exclusivo de las predeterminadas
        categoria.ambito = (
            AmbitoCategoria.EMPRESA if self.usuario.es_empresa else AmbitoCategoria.PERSONAL
        )
        if commit:
            categoria.save()
        return categoria
