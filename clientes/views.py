from django.db.models import Q
from rest_framework import status, viewsets
from core.permissions import EsCliente, PermisoPorAccion
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.exceptions import PermissionDenied

from core.mixins import BajaLogicaMixin
from . import services
from .models import Cliente
from .serializers import (
    CambiarMiPasswordSerializer,
    ClienteSerializer,
    EditarMiPerfilSerializer,
    MiPerfilSerializer,
)


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

class MiPerfilAPIView(APIView):
    """
    /api/clientes/mi-perfil/   (solo clientes de la tienda)
      GET    mis datos
      PATCH  modifico mis datos (solo los campos que mando)
    """
    permission_classes = [EsCliente]

    def get(self, request):
        return Response(MiPerfilSerializer(request.user.cliente).data)

    def patch(self, request):
        cliente = request.user.cliente
        entrada = EditarMiPerfilSerializer(instance=cliente, data=request.data)
        entrada.is_valid(raise_exception=True)

        cliente = services.actualizar_mi_perfil(cliente=cliente, datos=entrada.validated_data)
        return Response(MiPerfilSerializer(cliente).data)


class CambiarMiPasswordAPIView(APIView):
    """POST /api/clientes/mi-perfil/password/  {password_actual, password_nueva, password_repetida}"""
    permission_classes = [EsCliente]

    def post(self, request):
        entrada = CambiarMiPasswordSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        services.cambiar_mi_password(
            usuario=request.user,
            actual=entrada.validated_data["password_actual"],
            nueva=entrada.validated_data["password_nueva"],
        )
        return Response({"mensaje": "Contraseña actualizada."}, status=status.HTTP_200_OK)