from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CompraViewSet,
    DetalleCompraViewSet,
)

router = DefaultRouter()

router.register("compras", CompraViewSet, basename="compra")
router.register(
    "detalles-compras",
    DetalleCompraViewSet,
    basename="detalle-compra"
)

urlpatterns = [
    path("", include(router.urls)),
]