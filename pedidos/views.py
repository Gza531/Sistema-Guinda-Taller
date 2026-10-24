from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from core.permissions import PermisoPorAccion

from . import services
from .models import Pedido
from .serializers import (
    PedidoSerializer,
    NuevoPedidoSerializer,
    CambiarEstadoSerializer,
    CancelarPedidoSerializer,
    EntregarPedidoSerializer,
)

def _entero(valor, campo):
    try:
        return int(valor)
    except ValueError:
        raise ValidationError({
            campo: "Debe ser un número entero."
        })


def _fecha(valor, campo):
    try:
        fecha = parse_date(valor)
    except ValueError:
        fecha = None

    if fecha is None:
        raise ValidationError({
            campo: "Use el formato AAAA-MM-DD, por ejemplo 2026-10-18."
        })

    return fecha

class PedidoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    API para gestionar los pedidos de Guinda.

    GET /api/pedidos/pedidos/
    POST /api/pedidos/pedidos/
    GET /api/pedidos/pedidos/{id}/
    POST /api/pedidos/pedidos/{id}/estado/
    POST /api/pedidos/pedidos/{id}/cancelar/
    """

    permission_classes = [PermisoPorAccion]
    permisos = {
        "list": "ver_pedidos",
        "retrieve": "ver_pedidos",
        "create": "crear_pedido",
        "estado": "gestionar_pedido",
        "cancelar": "gestionar_pedido",
        "entregar": "gestionar_pedido",  # lo agrega Emi con pedido -> venta
    }
    serializer_class = PedidoSerializer

    def get_queryset(self):
        qs = (
            Pedido.objects
            .select_related("cliente", "usuario")
            .prefetch_related(
                "detallepedido_set__producto",
                "venta_set"
            )
            .order_by("-fecha")
        )

        p = self.request.query_params

        if p.get("canal"):
            qs = qs.filter(canal=p["canal"].upper())

        if p.get("estado"):
            qs = qs.filter(estado=p["estado"].upper())

        if p.get("cliente"):
            qs = qs.filter(cliente_id=_entero(p["cliente"], "cliente"))

        if p.get("desde"):
            qs = qs.filter(fecha__date__gte=_fecha(p["desde"], "desde"))

        if p.get("hasta"):
            qs = qs.filter(fecha__date__lte=_fecha(p["hasta"], "hasta"))

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return NuevoPedidoSerializer

        if self.action == "estado":
            return CambiarEstadoSerializer

        if self.action == "cancelar":
            return CancelarPedidoSerializer

        if self.action == "entregar":
            return EntregarPedidoSerializer

        return PedidoSerializer

    def create(self, request):
        entrada = NuevoPedidoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        d = entrada.validated_data

        pedido = services.crear_pedido(
            cliente=d["cliente"],
            canal=d["canal"],
            items=d["items"],
            usuario=request.user,
            observaciones=d.get("observaciones") or None,
        )

        pedido = self.get_queryset().get(pk=pedido.pk)

        return Response(
            PedidoSerializer(pedido).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=["post"])
    def estado(self, request, pk=None):
        pedido = self.get_object()

        entrada = CambiarEstadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        services.cambiar_estado(
            pedido=pedido,
            estado=entrada.validated_data["estado"],
        )

        pedido = self.get_queryset().get(pk=pedido.pk)

        return Response(PedidoSerializer(pedido).data)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        pedido = self.get_object()

        entrada = CancelarPedidoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        services.cancelar_pedido(
            pedido=pedido,
            motivo=entrada.validated_data["motivo"],
        )

        pedido = self.get_queryset().get(pk=pedido.pk)

        return Response(PedidoSerializer(pedido).data)

    @action(detail=True, methods=["post"])
    def entregar(self, request, pk=None):
        pedido = self.get_object()

        entrada = EntregarPedidoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        d = entrada.validated_data

        services.entregar_pedido(
            pedido=pedido,
            usuario=request.user,
            pagos=d["pagos"],
            entrega=d["entrega"],
            direccion_entrega=d.get("direccion_entrega") or None,
            costo_envio=d.get("costo_envio"),
        )

        pedido = self.get_queryset().get(pk=pedido.pk)

        return Response(PedidoSerializer(pedido).data)
