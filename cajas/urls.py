from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MetodoPagoViewSet

router = DefaultRouter()
router.register("metodos-pago", MetodoPagoViewSet, basename="metodo-pago")

urlpatterns = [
    path("", include(router.urls)),
]