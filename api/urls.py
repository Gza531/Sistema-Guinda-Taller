from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    EstadoAPIView,
    ProductoViewSet,
    LoginAPIView,
    RegistroAPIView,
    PerfilAPIView,
    MarcaViewSet,
    CategoriaViewSet,
    LogoutAPIView,
)


router = DefaultRouter()
router.register(r'productos', ProductoViewSet)
router.register(
    r"marcas",
    MarcaViewSet
)
router.register(
    r"categorias",
    CategoriaViewSet
)



urlpatterns = [
    path('estado/', EstadoAPIView.as_view(), name='api-estado'),
    path("registro/", RegistroAPIView.as_view(), name="api-registro"),
    path("login/", LoginAPIView.as_view(), name="api-login"),
    path("logout/", LogoutAPIView.as_view(), name="api-logout"),
    path("perfil/", PerfilAPIView.as_view(), name="api-perfil"),
    
    path(
    "token/refresh/",
    TokenRefreshView.as_view(),
    name="token_refresh"
),
    path('', include(router.urls)),
]