from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import EstadoAPIView, ProductoViewSet


router = DefaultRouter()
router.register(r'productos', ProductoViewSet)


urlpatterns = [
    path('estado/', EstadoAPIView.as_view(), name='api-estado'),
    path('', include(router.urls)),
]