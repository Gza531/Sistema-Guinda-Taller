from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import BajaLogicaMixin
from . import services
from .models import AperturaCierreCaja, Caja, MetodoPago
from .serializers import (
    AbrirCajaSerializer, CajaSerializer, MetodoPagoSerializer, SesionCajaSerializer,
)


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

    def destroy(self, request, *args, **kwargs):
        if services.sesion_abierta(self.get_object()):
            raise ValidationError({"caja": "No se puede dar de baja una caja abierta. Ciérrela primero."})
        return super().destroy(request, *args, **kwargs)


class SesionCajaViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    """
    /api/cajas/sesiones/
      GET   historial de aperturas y cierres (filtros: ?caja=<id>, ?abiertas=true)
      POST  abre una caja: {"caja": 1, "monto_inicial": "10000.00", "observaciones": "..."}
    Las sesiones no se editan ni se borran. El cierre va a ser /sesiones/{id}/cerrar/.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = AperturaCierreCaja.objects.select_related("caja", "usuario").order_by("-fecha_apertura")
        p = self.request.query_params
        if p.get("caja"):
            qs = qs.filter(caja_id=p["caja"])
        if p.get("abiertas") in ("true", "1"):
            qs = qs.filter(fecha_cierre__isnull=True)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return AbrirCajaSerializer
        return SesionCajaSerializer

    def create(self, request):
        entrada = AbrirCajaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        sesion = services.abrir_caja(
            caja=d["caja"],
            usuario=request.user,
            monto_inicial=d["monto_inicial"],
            observaciones=d.get("observaciones") or None,
        )
        return Response(SesionCajaSerializer(sesion).data, status=status.HTTP_201_CREATED)