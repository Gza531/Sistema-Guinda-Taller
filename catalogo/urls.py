from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CategoriaViewSet, MarcaViewSet, ProductoViewSet

# Se incluye bajo /api/ (ver config/urls.py), así que las rutas siguen siendo
# /api/productos/, /api/marcas/ y /api/categorias/: el front no cambia.
router = DefaultRouter()
router.register(r"productos", ProductoViewSet)
router.register(r"marcas", MarcaViewSet)
router.register(r"categorias", CategoriaViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
