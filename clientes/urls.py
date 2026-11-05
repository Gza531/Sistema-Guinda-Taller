from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CambiarMiPasswordAPIView, ClienteViewSet, MiPerfilAPIView, MiFavoritoAPIView, MisFavoritosAPIView

router = DefaultRouter()
router.register("clientes", ClienteViewSet, basename="cliente")

urlpatterns = [
        path(
        "mis-favoritos/",
        MisFavoritosAPIView.as_view(),
        name="mis-favoritos"
    ),

    path(
        "mis-favoritos/<int:id_producto>/",
        MiFavoritoAPIView.as_view(),
        name="mi-favorito"
    ),
    path("mi-perfil/", MiPerfilAPIView.as_view(), name="mi-perfil"),
    path("mi-perfil/password/", CambiarMiPasswordAPIView.as_view(), name="mi-perfil-password"),
    path("", include(router.urls)),
]
