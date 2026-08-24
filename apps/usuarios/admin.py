from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm

from .models import ConfiguracionUsuario, Empresa, Usuario


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nit", "telefono", "activa", "creado_en")
    list_filter = ("activa",)
    search_fields = ("nombre", "nit")


class ConfiguracionInline(admin.StackedInline):
    model = ConfiguracionUsuario
    can_delete = False
    verbose_name_plural = "Configuración"


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """Panel del administrador (§27).

    Puede consultar usuarios y activarlos o desactivarlos, pero no ve
    las obligaciones de nadie: esas se gestionan solo desde la aplicación.
    """

    change_password_form = AdminPasswordChangeForm
    inlines = [ConfiguracionInline]

    list_display = ("email", "nombre", "tipo_usuario", "empresa", "is_active", "date_joined")
    list_filter = ("tipo_usuario", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "nombre", "empresa__nombre")
    ordering = ("email",)
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre", "tipo_usuario", "empresa")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "nombre", "tipo_usuario", "password1", "password2"),
            },
        ),
    )

    @admin.action(description="Activar usuarios seleccionados")
    def activar(self, request, queryset):
        actualizados = queryset.update(is_active=True)
        self.message_user(request, f"{actualizados} usuario(s) activado(s).")

    @admin.action(description="Desactivar usuarios seleccionados")
    def desactivar(self, request, queryset):
        actualizados = queryset.update(is_active=False)
        self.message_user(request, f"{actualizados} usuario(s) desactivado(s).")

    actions = ["activar", "desactivar"]
