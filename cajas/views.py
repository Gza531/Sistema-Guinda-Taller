from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.mixins import BajaLogicaMixin
from .models import Caja, MetodoPago
from .serializers import CajaSerializer, MetodoPagoSerializer


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

class CajaViewSet(BajaLogicaMixin, viewsets.ModelViewSet):
    """
    /api/cajas/cajas/
      GET     lista (filtros: ?tipo=presencial|online, ?estado=true|false)
      POST    alta
      PATCH   /{id}/ modificación
      DELETE  /{id}/ baja lógica
    """

    queryset = Caja.objects.order_by("nombre")
    serializer_class = CajaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        tipo = self.request.query_params.get("tipo")
        if tipo:
            qs = qs.filter(tipo_caja=tipo.upper())
        return qs