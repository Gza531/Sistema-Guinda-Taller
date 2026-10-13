from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import MovimientoStockViewSet, StockViewSet

router = DefaultRouter()
router.register("existencias", StockViewSet, basename="stock")
router.register("movimientos", MovimientoStockViewSet, basename="movimiento-stock")

urlpatterns = [
    path("", include(router.urls)),
]