from rest_framework.routers import DefaultRouter

from .views import PromocionViewSet


router = DefaultRouter()
router.register(
    "promociones",
    PromocionViewSet,
    basename="promocion"
)

urlpatterns = router.urls