from rest_framework import viewsets
from core.permissions import EsPersonal

from core.mixins import BajaLogicaMixin

from .models import Proveedor, ProveedorXProducto
from .serializers import ProveedorSerializer, ProveedorXProductoSerializer


class ProveedorViewSet(BajaLogicaMixin,viewsets.ModelViewSet):
    queryset = Proveedor.objects.all().order_by("razon_social")
    serializer_class = ProveedorSerializer
    permission_classes = [EsPersonal]


class ProveedorXProductoViewSet(viewsets.ModelViewSet):
    queryset = ProveedorXProducto.objects.select_related(
        "proveedor",
        "producto"
    ).order_by("proveedor__razon_social", "producto__nombre")

    serializer_class = ProveedorXProductoSerializer
    permission_classes = [EsPersonal]