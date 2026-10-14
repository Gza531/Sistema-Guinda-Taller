from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import MetodoPago
from .serializers import MetodoPagoSerializer

from core.mixins import BajaLogicaMixin


class MetodoPagoViewSet(BajaLogicaMixin, viewsets.ModelViewSet):
    """
    /api/cajas/metodos-pago/
      GET           lista (filtro opcional: ?estado=true o ?estado=false)
      POST          crea un método de pago
      GET    /{id}/ detalle
      PATCH  /{id}/ modifica; también sirve para reactivarlo: {"estado": true}
      DELETE /{id}/ NO borra: lo da de baja (estado = False)
    """

    serializer_class = MetodoPagoSerializer

    def get_queryset(self):
        qs = MetodoPago.objects.order_by("nombre")
        estado = self.request.query_params.get("estado")
        if estado in ("true", "1"):
            qs = qs.filter(estado=True)
        elif estado in ("false", "0"):
            qs = qs.filter(estado=False)
        return qs

