from decimal import Decimal

from django import forms
from django.utils import timezone

from .enums import AmbitoCategoria, Prioridad
from .models import Categoria, Obligacion

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


class ObligacionForm(forms.ModelForm):
    """Registro y edición de una obligación (§10).

    Dos puntos de seguridad:
      - el selector de categorías se limita a las visibles para el usuario,
        de modo que no puede asignar la categoría privada de otro;
      - el propietario nunca llega desde el formulario, lo fija la vista.
    """

    class Meta:
        model = Obligacion
        fields = (
            "concepto",
            "monto",
            "fecha_vencimiento",
            "categoria",
            "prioridad_usuario",
            "descripcion",
            "enlace_pago",
            "proveedor",
            "referencia",
        )
        widgets = {
            "concepto": forms.TextInput(attrs={"placeholder": "Internet"}),
            "fecha_vencimiento": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "monto": forms.NumberInput(attrs={"step": "0.01", "min": "0.01",
                                              "placeholder": "120000"}),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "enlace_pago": forms.URLInput(
                attrs={"placeholder": "https://pagos.miempresa.com/factura"}
            ),
            "referencia": forms.TextInput(attrs={"placeholder": "FAC-00123"}),
        }
        labels = {
            "prioridad_usuario": "¿Qué tan importante es para ti?",
            "enlace_pago": "Enlace de pago (opcional)",
        }
        help_texts = {
            "enlace_pago": "PAYRECORD no realiza pagos: solo te lleva al enlace que indiques.",
        }

    recordatorios = forms.MultipleChoiceField(
        label="Avísame antes del vencimiento",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Recibirás una notificación dentro de PAYRECORD.",
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

        self.fields["categoria"].queryset = Categoria.objects.disponibles_para(usuario)
        self.fields["categoria"].empty_label = "Elige una categoría"

        # Los campos empresariales solo aplican a ese tipo de cuenta (§7).
        if not usuario.es_empresa:
            del self.fields["proveedor"]
            del self.fields["referencia"]

        for campo in ("descripcion", "enlace_pago"):
            self.fields[campo].required = False

        self._preparar_recordatorios(usuario)

    def _preparar_recordatorios(self, usuario):
        """Casillas de recordatorio (§13), marcadas según el caso.

        Al crear se proponen las preferencias del usuario; al editar, lo que
        esa obligación ya tenga configurado.
        """
        from apps.recordatorios.enums import DIAS_RECORDATORIO

        self.fields["recordatorios"].choices = [
            (str(dias), etiqueta) for dias, etiqueta in DIAS_RECORDATORIO
        ]

        if self.instance.pk:
            actuales = self.instance.reglas_recordatorio.filter(activa=True).values_list(
                "dias_antes", flat=True
            )
            self.fields["recordatorios"].initial = [str(d) for d in actuales]
        else:
            configuracion = getattr(usuario, "configuracion", None)
            propuestos = configuracion.dias_recordatorio_default if configuracion else [7, 1, 0]
            self.fields["recordatorios"].initial = [str(d) for d in propuestos]

    def clean_recordatorios(self):
        from apps.recordatorios.enums import DIAS_VALIDOS

        elegidos = self.cleaned_data.get("recordatorios") or []
        try:
            dias = {int(valor) for valor in elegidos}
        except (TypeError, ValueError):
            raise forms.ValidationError("Selecciona opciones válidas.")

        if not dias.issubset(set(DIAS_VALIDOS)):
            raise forms.ValidationError("Selecciona opciones válidas.")
        return sorted(dias, reverse=True)

    def clean_monto(self):
        monto = self.cleaned_data["monto"]
        if monto <= Decimal("0"):
            raise forms.ValidationError("El valor debe ser mayor que cero.")
        if monto >= Decimal("1000000000000"):
            raise forms.ValidationError("El valor es demasiado grande.")
        return monto

    def clean_fecha_vencimiento(self):
        """Se admiten fechas pasadas: sirve para registrar deudas ya vencidas.

        Solo se descartan fechas absurdamente lejanas, que suelen ser errores
        de digitación.
        """
        fecha = self.cleaned_data["fecha_vencimiento"]
        limite = timezone.localdate().replace(year=timezone.localdate().year + 50)
        if fecha > limite:
            raise forms.ValidationError("Revisa la fecha: está demasiado lejos en el futuro.")
        return fecha

    def clean_concepto(self):
        return self.cleaned_data["concepto"].strip()

    def save(self, commit=True):
        from apps.recordatorios.services.generacion import aplicar_reglas

        obligacion = super().save(commit=False)
        obligacion.usuario = self.usuario
        # La empresa se copia del usuario: nunca llega desde el formulario.
        obligacion.empresa = self.usuario.empresa

        if commit:
            obligacion.save()
            aplicar_reglas(obligacion, self.cleaned_data.get("recordatorios") or [])
            # Al cambiar la fecha, los avisos de la fecha anterior dejan de valer.
            from apps.recordatorios.services.generacion import sincronizar

            sincronizar(obligacion)

        return obligacion


class FiltroObligacionesForm(forms.Form):
    """Filtros del listado. Todos opcionales."""

    ESTADOS = [("", "Todos los estados")]

    q = forms.CharField(
        label="Buscar",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Concepto, proveedor o referencia"}),
    )
    estado = forms.ChoiceField(label="Estado", required=False, choices=ESTADOS)
    categoria = forms.ModelChoiceField(
        label="Categoría",
        required=False,
        queryset=Categoria.objects.none(),
        empty_label="Todas las categorías",
    )
    prioridad = forms.ChoiceField(
        label="Prioridad",
        required=False,
        choices=[("", "Cualquier prioridad")] + list(Prioridad.choices),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .managers import ESTADOS_FILTRABLES

        self.fields["estado"].choices = self.ESTADOS + [
            (valor, etiqueta) for valor, etiqueta in ESTADOS_FILTRABLES
        ]
        if usuario:
            self.fields["categoria"].queryset = Categoria.objects.disponibles_para(usuario)
