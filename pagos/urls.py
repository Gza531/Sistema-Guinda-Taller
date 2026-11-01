from django.urls import path
from .views import ConfiguracionTiendaAPIView
from .checkout_views import CheckoutAPIView
from .webhook_views import WebhookMercadoPagoAPIView

urlpatterns = [
    path(
        "configuracion/",
        ConfiguracionTiendaAPIView.as_view(),
        name="pagos-configuracion",
    ),

    path(
        "checkout/",
        CheckoutAPIView.as_view(),
        name="pagos-checkout",
    ),
    path(
        "webhook/",
        WebhookMercadoPagoAPIView.as_view(),
        name="pagos-webhook",
    ),
]
