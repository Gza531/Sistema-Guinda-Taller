from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .checkout_views import PagoNoDisponible
from .services import costo_envio_configurado


class ConfiguracionTiendaAPIView(APIView):
    """
    GET /api/pagos/configuracion/ → { "costo_envio": "5000.00" }

    Datos públicos que la tienda necesita mostrar antes de pagar.
    No hace falta sesión: el costo del envío no es un dato privado.
    El monto que se cobra lo vuelve a calcular el checkout (el front solo lo muestra).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            costo = costo_envio_configurado()
        except ImproperlyConfigured as error:
            raise PagoNoDisponible() from error

        return Response({"costo_envio": str(costo.quantize(Decimal("0.01")))})