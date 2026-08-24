from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction

from .models import ConfiguracionUsuario, Empresa, TipoUsuario, Usuario


class RegistroForm(UserCreationForm):
    """Registro unificado para usuario personal y empresa (§5, §6).

    Los campos de empresa solo son obligatorios cuando se elige ese tipo,
    de modo que no existan dos formularios distintos que mantener.
    """

    nombre = forms.CharField(
        label="Nombre completo",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "María Rodríguez"}),
    )
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"placeholder": "maria@example.com"}),
    )
    tipo_usuario = forms.ChoiceField(
        label="¿Cómo vas a usar PAYRECORD?",
        choices=TipoUsuario.choices,
        initial=TipoUsuario.PERSONAL,
        widget=forms.RadioSelect,
    )
    nombre_empresa = forms.CharField(
        label="Nombre o razón social",
        max_length=150,
        required=False,
    )
    nit = forms.CharField(label="NIT", max_length=30, required=False)

    class Meta:
        model = Usuario
        fields = ("nombre", "email", "tipo_usuario")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta registrada con este correo.")
        return email

    def clean_nit(self):
        nit = (self.cleaned_data.get("nit") or "").strip()
        if nit and Empresa.objects.filter(nit=nit).exists():
            raise forms.ValidationError("Ya existe una empresa registrada con este NIT.")
        return nit

    def clean(self):
        datos = super().clean()
        if datos.get("tipo_usuario") == TipoUsuario.EMPRESA:
            if not (datos.get("nombre_empresa") or "").strip():
                self.add_error(
                    "nombre_empresa",
                    "Indica el nombre de la empresa para registrar una cuenta empresarial.",
                )
        return datos

    @transaction.atomic
    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.email = self.cleaned_data["email"]
        usuario.nombre = self.cleaned_data["nombre"]
        usuario.tipo_usuario = self.cleaned_data["tipo_usuario"]

        if usuario.tipo_usuario == TipoUsuario.EMPRESA:
            usuario.empresa = Empresa.objects.create(
                nombre=self.cleaned_data["nombre_empresa"].strip(),
                nit=self.cleaned_data.get("nit") or None,
            )

        if commit:
            usuario.save()
        return usuario


class LoginForm(AuthenticationForm):
    """Autenticación por correo electrónico."""

    username = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "maria@example.com"}),
    )

    error_messages = {
        "invalid_login": "El correo o la contraseña no son correctos.",
        "inactive": "Esta cuenta está desactivada. Contacta al administrador.",
    }


class PerfilForm(forms.ModelForm):
    """Datos editables de la cuenta.

    El tipo de usuario no se incluye a propósito: cambiarlo dejaría
    obligaciones clasificadas en categorías de otro ámbito (riesgo R11).
    Solo el administrador puede cambiarlo desde el panel.
    """

    class Meta:
        model = Usuario
        fields = ("nombre", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe otra cuenta registrada con este correo.")
        return email


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ("nombre", "nit", "telefono")


class ConfiguracionForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionUsuario
        fields = ("dias_proximo_vencimiento", "notificaciones_app", "notificaciones_email")

    def clean_dias_proximo_vencimiento(self):
        dias = self.cleaned_data["dias_proximo_vencimiento"]
        if not 1 <= dias <= 60:
            raise forms.ValidationError("Indica un valor entre 1 y 60 días.")
        return dias
