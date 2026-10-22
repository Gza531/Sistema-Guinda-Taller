from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EnvioViewSet


router = DefaultRouter()
router.register("envios", EnvioViewSet, basename="envio")

urlpatterns = [
    path("", include(router.urls)),
]
