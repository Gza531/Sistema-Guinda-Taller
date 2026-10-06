from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import EstadoAPIView, ProductoViewSet, LoginAPIView, PerfilAPIView


router = DefaultRouter()
router.register(r'productos', ProductoViewSet)


urlpatterns = [
    path('estado/', EstadoAPIView.as_view(), name='api-estado'),
    path("login/", LoginAPIView.as_view(), name="api-login"),
    path("perfil/", PerfilAPIView.as_view(), name="api-perfil"),
    
    path(
    "token/refresh/",
    TokenRefreshView.as_view(),
    name="token_refresh"
),
    path('', include(router.urls)),
]