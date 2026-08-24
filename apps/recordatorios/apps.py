from django.apps import AppConfig


class RecordatoriosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recordatorios"
    verbose_name = "Recordatorios"

    def ready(self):
        from . import signals  # noqa: F401
