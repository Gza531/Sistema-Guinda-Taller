from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.mixins import BajaLogicaMixin

from .models import Proveedor, ProveedorXProducto
from .serializers import ProveedorSerializer, ProveedorXProductoSerializer


class ProveedorViewSet(BajaLogicaMixin,viewsets.ModelViewSet):
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
