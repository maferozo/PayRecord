from django.contrib import admin

from .models import Categoria, Obligacion


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    """§27: el administrador consulta el catálogo y mantiene las predeterminadas."""

    list_display = ("nombre", "ambito", "peso_prioridad", "usuario", "activa")
    list_filter = ("ambito", "activa", ("usuario", admin.EmptyFieldListFilter))
    search_fields = ("nombre", "codigo")
    ordering = ("ambito", "nombre")

    fieldsets = (
        (None, {"fields": ("nombre", "codigo", "ambito", "activa")}),
        ("Presentación", {"fields": ("color", "icono")}),
        ("Prioridad", {"fields": ("peso_prioridad",)}),
        ("Propiedad", {
            "fields": ("usuario",),
            "description": "Vacío indica que es una categoría predeterminada del sistema.",
        }),
    )


@admin.register(Obligacion)
class ObligacionAdmin(admin.ModelAdmin):
    """Solo lectura desde el panel.

    §27 pide que el administrador no acceda innecesariamente a información
    privada: puede verificar la integridad de los datos, pero no editar ni
    borrar las obligaciones de nadie.
    """

    list_display = ("concepto", "usuario", "monto", "fecha_vencimiento", "pagada", "categoria")
    list_filter = ("pagada", "prioridad_usuario", "categoria__ambito")
    search_fields = ("concepto", "usuario__email", "proveedor", "referencia")
    date_hierarchy = "fecha_vencimiento"
    ordering = ("-fecha_vencimiento",)

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
