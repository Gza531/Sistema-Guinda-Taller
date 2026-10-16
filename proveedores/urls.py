from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProveedorViewSet, ProveedorXProductoViewSet

router = DefaultRouter()
router.register("proveedores", ProveedorViewSet, basename="proveedor")
router.register("proveedores-productos", ProveedorXProductoViewSet, basename="proveedor-producto")

urlpatterns = [
    path("", include(router.urls)),
]
