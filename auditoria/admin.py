from django.contrib import admin

from .models import Auditoria


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    """Solo consulta: la auditoría no se carga, no se edita ni se borra (RIR)."""
    list_display = ("fecha_hora", "usuario", "accion", "tabla_afectada", "id_registro_afectado")
    list_filter = ("accion", "tabla_afectada")
    search_fields = ("usuario__username", "tabla_afectada")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
