from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "auditoria"

    def ready(self):
        # Conecta las señales que registran altas, modificaciones y bajas
        from .signals import conectar
        conectar()
