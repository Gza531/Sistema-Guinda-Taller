from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.mixins import BajaLogicaMixin
from core.permissions import EsPersonal

from . import services
from .models import Promocion
from .serializers import PromocionSerializer, PromocionEntradaSerializer

class PromocionViewSet(BajaLogicaMixin, viewsets.ModelViewSet):
    """
    API para administrar las promociones de Guinda.

    El personal puede crear, consultar, editar y desactivar promociones.
    El listado de promociones vigentes será público.
    """

    permission_classes = [EsPersonal]

    queryset = (
        Promocion.objects
        .prefetch_related("promocionproducto_set__producto")
        .order_by("-fecha_inicio", "nombre")
    )

    def get_permissions(self):
        if self.action == "vigentes":
            return [AllowAny()]

        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
          return PromocionEntradaSerializer

        return PromocionSerializer

    def _respuesta(self, promo, codigo=status.HTTP_200_OK):
        promo = (
            Promocion.objects
            .prefetch_related("promocionproducto_set__producto")
            .get(pk=promo.pk)
        )

        return Response(
            PromocionSerializer(promo).data,
            status=codigo
        )

    def create(self, request, *args, **kwargs):
        entrada = PromocionEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        promocion = services.crear_promocion(
            **entrada.validated_data
        )

        return self._respuesta(
            promocion,
            status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)

        promo = self.get_object()

        entrada = PromocionEntradaSerializer(
            data=request.data,
            partial=partial
        )
        entrada.is_valid(raise_exception=True)

        promo = services.actualizar_promocion(
            promocion=promo,
            **entrada.validated_data
        )

        return self._respuesta(promo)

    @action(detail=False, methods=["get"])
    def vigentes(self, request):
        qs = (
            services.vigentes()
            .prefetch_related("promocionproducto_set__producto")
            .order_by("fecha_fin")
        )

        return Response(
            PromocionSerializer(qs, many=True).data
        )