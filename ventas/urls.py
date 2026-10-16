from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Acá se van a registrar los endpoints de ventas (venta presencial, anulación).

urlpatterns = [
    path("", include(router.urls)),
]
