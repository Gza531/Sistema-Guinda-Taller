from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import Proveedor, ProveedorXProducto, Compra, DetalleCompra
from .serializers import (
    ProveedorSerializer,
    ProveedorXProductoSerializer,
    CompraSerializer,
    DetalleCompraSerializer,
    CrearCompraSerializer,
)


class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all().order_by("razon_social")
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated]


class ProveedorXProductoViewSet(viewsets.ModelViewSet):
    queryset = ProveedorXProducto.objects.select_related(
        "proveedor",
        "producto"
    ).all()

    serializer_class = ProveedorXProductoSerializer
    permission_classes = [IsAuthenticated]


class CompraViewSet(viewsets.ModelViewSet):
    queryset = Compra.objects.select_related(
        "proveedor",
        "usuario"
    ).all().order_by("-fecha")

    serializer_class = CompraSerializer
    permission_classes = [IsAuthenticated]
    def create(self, request, *args, **kwargs):
        entrada = CrearCompraSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        datos = entrada.validated_data

        compra = services.crear_compra(
            proveedor=datos["proveedor"],
            usuario=request.user,
            detalles=datos["detalles"],
            numero_factura=datos.get("numero_factura"),
            observaciones=datos.get("observaciones"),
        )

        salida = CompraSerializer(compra)

        return Response(
            salida.data,
            status=status.HTTP_201_CREATED
        )
    @action(detail=True, methods=["post"], url_path="recibir")
    def recibir(self, request, pk=None):
        compra = self.get_object()

        compra = services.recibir_compra(
            compra=compra,
            usuario=request.user
        )

        serializer = self.get_serializer(compra)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class DetalleCompraViewSet(viewsets.ModelViewSet):
    queryset = DetalleCompra.objects.select_related(
        "compra",
        "producto"
    ).all()

    serializer_class = DetalleCompraSerializer
    permission_classes = [IsAuthenticated]