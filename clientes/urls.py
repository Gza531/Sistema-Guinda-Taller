from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CambiarMiPasswordAPIView, ClienteViewSet, MiPerfilAPIView

router = DefaultRouter()
router.register("clientes", ClienteViewSet, basename="cliente")

urlpatterns = [
    path("mi-perfil/", MiPerfilAPIView.as_view(), name="mi-perfil"),
    path("mi-perfil/password/", CambiarMiPasswordAPIView.as_view(), name="mi-perfil-password"),
    path("", include(router.urls)),
]
