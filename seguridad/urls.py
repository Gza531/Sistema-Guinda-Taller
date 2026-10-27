from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EmpleadoViewSet, RolesAPIView


router = DefaultRouter()
router.register("empleados", EmpleadoViewSet, basename="empleado")

urlpatterns = [
    path("roles/", RolesAPIView.as_view(), name="roles"),
    path("", include(router.urls)),
]