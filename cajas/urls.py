from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CajaViewSet, MetodoPagoViewSet, SesionCajaViewSet, MovimientoCajaViewSet

router = DefaultRouter()
router.register("cajas", CajaViewSet, basename="caja")
router.register("sesiones", SesionCajaViewSet, basename="sesion-caja")
router.register("movimientos", MovimientoCajaViewSet, basename="movimiento-caja")
router.register("metodos-pago", MetodoPagoViewSet, basename="metodo-pago")

urlpatterns = [
    path("", include(router.urls)),
]