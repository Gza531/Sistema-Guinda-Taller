from django.db.models import Q
from rest_framework import viewsets
from core.permissions import PermisoPorAccion

from rest_framework.exceptions import PermissionDenied

from core.mixins import BajaLogicaMixin
from .models import Cliente
from .serializers import ClienteSerializer


class ClienteViewSet(BajaLogicaMixin, viewsets.ModelViewSet):
    """
    /api/clientes/
      GET     lista (filtros: ?buscar=texto, ?estado=true|false)
      POST    alta
      PATCH   /{id}/ modificación (también reactivación: {"estado": true})
      DELETE  /{id}/ baja lógica
    """

    queryset = Cliente.objects.order_by("apellido", "nombre")
    serializer_class = ClienteSerializer
    permission_classes = [PermisoPorAccion]  # datos personales: solo el personal
    permisos = {
        "list": "ver_clientes",
        "retrieve": "ver_clientes",
        "create": "editar_clientes",
        "update": "editar_clientes",
        "partial_update": "editar_clientes",
        "destroy": "baja_cliente",  # baja lógica
    }

    def get_queryset(self):
        qs = super().get_queryset()  # ya trae el filtro ?estado= del mixin
        buscar = self.request.query_params.get("buscar")
        if buscar:
            qs = qs.filter(
                Q(nombre__icontains=buscar)
                | Q(apellido__icontains=buscar)
                | Q(nro_documento__icontains=buscar)
            )
        return qs

    def _bloquear_consumidor_final(self):
        if self.get_object().es_consumidor_final:
            raise PermissionDenied("El cliente «Consumidor Final» no se puede modificar ni dar de baja.")

    def update(self, request, *args, **kwargs):
        self._bloquear_consumidor_final()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._bloquear_consumidor_final()
        return super().destroy(request, *args, **kwargs)
