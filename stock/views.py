from django.db.models import F
from rest_framework import mixins, status, viewsets
from core.permissions import EsPersonal
from rest_framework.response import Response

from . import services
from .models import MovimientoStock, Stock
from .serializers import MovimientoStockSerializer, NuevoMovimientoSerializer, StockSerializer


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockSerializer
    permission_classes = [EsPersonal]

    def get_queryset(self):
        stock = Stock.objects.select_related("producto").order_by("producto__nombre", "ubicacion")
        filtros = self.request.query_params

        if filtros.get("ubicacion"):
            stock = stock.filter(ubicacion=filtros["ubicacion"].upper())

        if filtros.get("buscar"):
            stock = stock.filter(producto__nombre__icontains=filtros["buscar"])

        if filtros.get("bajo_minimo") == "true":
            stock = stock.filter(cantidad_actual__lte=F("stock_minimo"))

        return stock


class MovimientoStockViewSet(mixins.ListModelMixin,
                             mixins.RetrieveModelMixin,
                             viewsets.GenericViewSet):
    permission_classes = [EsPersonal]

    def get_queryset(self):
        return MovimientoStock.objects.select_related("stock__producto", "usuario").order_by("-fecha")

    def get_serializer_class(self):
        if self.action == "create":
            return NuevoMovimientoSerializer
        return MovimientoStockSerializer

    def create(self, request):
        # 1. Validar lo que mandó React
        datos = NuevoMovimientoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        if d["tipo_movimiento"] == "REPOSICION":
            movimientos = services.registrar_reposicion(
                producto=d["producto"],
                origen=d["ubicacion"],
                cantidad=d["cantidad"],
                usuario=request.user,
                motivo=d.get("motivo") or None,
            )
            return Response(
                MovimientoStockSerializer(movimientos, many=True).data,
                status=status.HTTP_201_CREATED,
            )

        # 2. Elegir qué regla de negocio aplicar
        if d["tipo_movimiento"] == "ENTRADA":
            registrar = services.registrar_entrada
        else:
            registrar = services.registrar_salida

        # 3. Pedirle al servicio que haga el trabajo
        movimiento = registrar(
            producto=d["producto"],
            ubicacion=d["ubicacion"],
            cantidad=d["cantidad"],
            usuario=request.user,
            motivo=d.get("motivo") or None,
        )

        # 4. Responder con el movimiento registrado
        return Response(MovimientoStockSerializer(movimiento).data, status=status.HTTP_201_CREATED)