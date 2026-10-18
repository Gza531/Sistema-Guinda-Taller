from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PedidoViewSet


router = DefaultRouter()
router.register("pedidos", PedidoViewSet, basename="pedido")

urlpatterns = [
    path("", include(router.urls)),
]