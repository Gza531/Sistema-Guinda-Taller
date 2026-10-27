from django.urls import path

from .checkout_views import CheckoutAPIView

urlpatterns = [
    path(
        "checkout/",
        CheckoutAPIView.as_view(),
        name="pagos-checkout",
    ),
]
