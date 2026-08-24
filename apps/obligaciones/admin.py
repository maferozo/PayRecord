from django.contrib import admin

from .models import Categoria


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
