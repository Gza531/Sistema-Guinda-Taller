from datetime import date

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from core.permissions import PermisoPorAccion

from .models import Auditoria
from .serializers import AuditoriaSerializer


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Consulta de la auditoría (solo la Dueña). No se crea, edita ni borra desde la API.

    GET /api/auditoria/auditorias/?usuario=&accion=&tabla=&desde=AAAA-MM-DD&hasta=AAAA-MM-DD
    """
    serializer_class = AuditoriaSerializer
    permission_classes = [PermisoPorAccion]
    permisos = {
        "list": "ver_auditoria",
        "retrieve": "ver_auditoria",
    }

    def get_queryset(self):
        qs = Auditoria.objects.select_related("usuario").order_by("-fecha_hora", "-id_auditoria")
        filtros = self.request.query_params

        if filtros.get("usuario"):
            qs = qs.filter(usuario_id=self._entero(filtros["usuario"], "usuario"))
        if filtros.get("accion"):
            qs = qs.filter(accion=filtros["accion"].upper())
        if filtros.get("tabla"):
            qs = qs.filter(tabla_afectada=filtros["tabla"])
        if filtros.get("desde"):
            qs = qs.filter(fecha_hora__date__gte=self._fecha(filtros["desde"], "desde"))
        if filtros.get("hasta"):
            qs = qs.filter(fecha_hora__date__lte=self._fecha(filtros["hasta"], "hasta"))
        return qs

    @staticmethod
    def _entero(valor, campo):
        if not valor.isdigit():
            raise ValidationError({campo: "Tiene que ser un número."})
        return int(valor)

    @staticmethod
    def _fecha(valor, campo):
        try:
            return date.fromisoformat(valor)
        except ValueError:
            raise ValidationError({campo: "Usá el formato AAAA-MM-DD."})
