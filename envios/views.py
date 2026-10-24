from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from core.permissions import PermisoPorAccion

from . import services
from .models import Envio
from .serializers import (
    EnvioSerializer,
    NuevoEnvioSerializer,
    EditarEnvioSerializer,
    CambiarEstadoEnvioSerializer,
)


class EnvioViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    API para administrar los envíos de ventas online.
    """

    permission_classes = [PermisoPorAccion]
    permisos = {
        "list": "ver_envios",
        "retrieve": "ver_envios",
        "create": "gestionar_envios",
        "partial_update": "gestionar_envios",
        "destroy": "gestionar_envios",
        "estado": "gestionar_envios",
    }

    def get_queryset(self):
        queryset = Envio.objects.select_related(
            "venta__cliente"
        ).order_by("-id_envio")

        estado = self.request.query_params.get("estado")
        venta = self.request.query_params.get("venta")
        empresa = self.request.query_params.get("empresa")

        if estado:
            queryset = queryset.filter(estado=estado.upper())

        if venta:
            try:
                venta_id = int(venta)
            except ValueError:
                raise ValidationError({
                    "venta": "Debe ser un número entero."
                })

            queryset = queryset.filter(venta_id=venta_id)

        if empresa:
            queryset = queryset.filter(
                empresa_transporte__icontains=empresa
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return NuevoEnvioSerializer

        if self.action == "partial_update":
            return EditarEnvioSerializer

        if self.action == "estado":
            return CambiarEstadoEnvioSerializer

        return EnvioSerializer


    def _respuesta(self, envio, codigo=200):
        envio = self.get_queryset().get(pk=envio.pk)

        serializer = EnvioSerializer(envio)

        return Response(
            serializer.data,
            status=codigo
        )

    def create(self, request):
        entrada = NuevoEnvioSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        envio = services.crear_envio(
            **entrada.validated_data
        )

        return self._respuesta(
            envio,
            codigo=status.HTTP_201_CREATED
        )


    def partial_update(self, request, pk=None):
        envio = self.get_object()

        entrada = EditarEnvioSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        envio = services.actualizar_envio(
            envio=envio,
            **entrada.validated_data
        )

        return self._respuesta(envio)

    def destroy(self, request, pk=None):
        envio = self.get_object()

        services.eliminar_envio(envio=envio)

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


    @action(detail=True, methods=["post"])
    def estado(self, request, pk=None):
        envio = self.get_object()

        entrada = CambiarEstadoEnvioSerializer(
            data=request.data
        )
        entrada.is_valid(raise_exception=True)

        envio = services.cambiar_estado(
            envio=envio,
            **entrada.validated_data
        )

        return self._respuesta(envio)
