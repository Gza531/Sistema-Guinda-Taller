from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MisComprasViewSet, VentaViewSet

router = DefaultRouter()
router.register("ventas", VentaViewSet, basename="venta")
router.register("mis-compras", MisComprasViewSet, basename="mi-compra")

urlpatterns = [
    path("", include(router.urls)),
]