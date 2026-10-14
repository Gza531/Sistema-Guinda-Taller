from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProveedorViewSet,
    ProveedorXProductoViewSet,
    CompraViewSet,
    DetalleCompraViewSet,
)

router = DefaultRouter()

router.register("proveedores", ProveedorViewSet, basename="proveedor")
router.register(
    "proveedores-productos",
    ProveedorXProductoViewSet,
    basename="proveedor-producto"
)
router.register("compras", CompraViewSet, basename="compra")
router.register(
    "detalles-compras",
    DetalleCompraViewSet,
    basename="detalle-compra"
)

urlpatterns = [
    path("", include(router.urls)),
]