from django.urls import path

from .checkout_views import CheckoutAPIView
from .webhook_views import WebhookMercadoPagoAPIView

urlpatterns = [
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
