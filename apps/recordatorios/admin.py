from django.contrib import admin

from .models import ConfiguracionRecordatorio, Notificacion, Recordatorio


@admin.register(ConfiguracionRecordatorio)
class ConfiguracionRecordatorioAdmin(admin.ModelAdmin):
    list_display = ("obligacion", "dias_antes", "canal", "activa")
    list_filter = ("canal", "activa", "dias_antes")
    search_fields = ("obligacion__concepto",)


@admin.register(Recordatorio)
class RecordatorioAdmin(admin.ModelAdmin):
    """Solo lectura: sirve para diagnosticar el proceso automático (§16).

    Los estados los cambia el generador, no una persona.
    """

    list_display = ("obligacion", "dias_antes", "fecha_programada", "canal",
                    "estado", "fecha_envio")
    list_filter = ("estado", "canal", "dias_antes")
    search_fields = ("obligacion__concepto", "obligacion__usuario__email")
    date_hierarchy = "fecha_programada"

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "usuario", "leida", "fecha_lectura", "creado_en")
    list_filter = ("leida",)
    search_fields = ("titulo", "usuario__email")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
