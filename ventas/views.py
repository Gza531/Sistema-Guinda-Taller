
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from core.permissions import EsPersonal
from rest_framework.response import Response

from . import services
from .models import Venta
from .serializers import AnularVentaSerializer, NuevaVentaSerializer, VentaSerializer


class VentaViewSet(mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   viewsets.GenericViewSet):
    """
    /api/ventas/ventas/
      GET   historial (filtros: ?tipo=, ?estado=, ?cliente=, ?numero=, ?desde=AAAA-MM-DD, ?hasta=AAAA-MM-DD)
      POST  venta presencial:
            {"caja": 1, "cliente": null,
             "items": [{"producto": 3, "cantidad": 2}],
             "pagos": [{"metodo_pago": 1, "monto": "5000.00"}, {"metodo_pago": 2, "monto": "3500.00"}]}
    POST  /{id}/anular/ : {"motivo": "El cliente devolvió el producto"}
      Las ventas no se editan ni se borran: se anulan.
    """

    permission_classes = [EsPersonal]

    def get_queryset(self):
        qs = (
            Venta.objects
            .select_related("cliente", "usuario")
            .prefetch_related("detalleventa_set__producto", "movimientocaja_set__metodo_pago")
            .order_by("-fecha")
        )
        p = self.request.query_params
        if p.get("tipo"):
            qs = qs.filter(tipo=p["tipo"].upper())
        if p.get("estado"):
            qs = qs.filter(estado=p["estado"].upper())
        if p.get("cliente"):
            qs = qs.filter(cliente_id=p["cliente"])
        if p.get("numero"):
            qs = qs.filter(numero_comprobante__icontains=p["numero"])
        if p.get("desde"):
            qs = qs.filter(fecha__date__gte=p["desde"])
        if p.get("hasta"):
            qs = qs.filter(fecha__date__lte=p["hasta"])
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return NuevaVentaSerializer
        if self.action == "anular":
            return AnularVentaSerializer
        return VentaSerializer

    def create(self, request):
        entrada = NuevaVentaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        venta = services.registrar_venta_presencial(
            usuario=request.user,
            caja=d["caja"],
            cliente=d.get("cliente"),
            items=d["items"],
            pagos=d["pagos"],
            observaciones=d.get("observaciones") or None,
        )
        venta = self.get_queryset().get(pk=venta.pk)  # recarga con detalles y pagos
        return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
          venta = self.get_object()
          entrada = AnularVentaSerializer(data=request.data)
          entrada.is_valid(raise_exception=True)
          services.anular_venta(
              venta=venta,
              usuario=request.user,
              motivo=entrada.validated_data["motivo"],
          )
          venta = self.get_queryset().get(pk=venta.pk)
          return Response(VentaSerializer(venta).data)