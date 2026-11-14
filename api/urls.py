from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    EstadoAPIView,
    LoginAPIView,
    RegistroAPIView,
    PerfilAPIView,
    LogoutAPIView,
)

from .password_reset_views import (
    RecuperarPasswordAPIView,
    ConfirmarRecuperacionAPIView,
)

urlpatterns = [
    path('estado/', EstadoAPIView.as_view(), name='api-estado'),
    path("registro/", RegistroAPIView.as_view(), name="api-registro"),
    path(
        "recuperar-password/",
        RecuperarPasswordAPIView.as_view(),
        name="recuperar-password",
    ),
    path(
        "recuperar-password/confirmar/",
        ConfirmarRecuperacionAPIView.as_view(),
        name="confirmar-recuperacion",
    ),
    path("login/", LoginAPIView.as_view(), name="api-login"),
    path("logout/", LogoutAPIView.as_view(), name="api-logout"),
    path("perfil/", PerfilAPIView.as_view(), name="api-perfil"),
    
    path(
    "token/refresh/",
    TokenRefreshView.as_view(),
    name="token_refresh"
),
]