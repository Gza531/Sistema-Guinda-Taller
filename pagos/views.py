from decimal import Decimal

from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .tarifas import PROVINCIAS, localidades_salta, numero_postal, tabla_tarifas, tarifa_envio, validar_destino


def _pesos(valor):
    return str(Decimal(valor).quantize(Decimal("0.01")))


class ConfiguracionTiendaAPIView(APIView):
    """
    GET /api/pagos/configuracion/ →
        { "tarifas_envio": [{ "zona": "Salta Capital", "alcance": "...", "costo": "3500.00" }, ...],
          "localidades_salta": [{ "nombre": "Cafayate", "codigo_postal": "4427" }, ...] }

    Datos públicos que la tienda y el panel muestran antes de cobrar un envío.
    No hace falta sesión: las tarifas no son un dato privado.
    El monto que se cobra lo vuelve a calcular el checkout (el front solo lo muestra).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        tarifas = [
            {**tarifa, "costo": _pesos(tarifa["costo"])}
            for tarifa in tabla_tarifas()
        ]
        return Response({"tarifas_envio": tarifas, "localidades_salta": localidades_salta()})


class DestinoSerializer(serializers.Serializer):
    provincia = serializers.ChoiceField(choices=PROVINCIAS)
    codigo_postal = serializers.CharField(max_length=8)
    localidad = serializers.CharField(max_length=60, required=False, allow_blank=True)

    def validate_codigo_postal(self, valor):
        valor = valor.strip().upper()
        if not numero_postal(valor):
            raise serializers.ValidationError("Usá 4 números (ej. 4400) o el formato A4400ABC.")
        return valor

    def validate(self, datos):
        error = validar_destino(datos["provincia"], datos.get("localidad", ""), datos["codigo_postal"])
        if error:
            raise serializers.ValidationError({"codigo_postal": error})
        return datos


class CostoEnvioAPIView(APIView):
    """
    GET /api/pagos/costo-envio/?provincia=Salta&localidad=Salta&codigo_postal=4400 →
        { "zona": "Salta Capital", "costo": "3500.00" }

    Lo usa el checkout para mostrar el costo apenas se carga el destino.
    Es el mismo cálculo que hace el checkout al cobrar.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        destino = DestinoSerializer(data=request.query_params)
        destino.is_valid(raise_exception=True)

        datos = destino.validated_data
        tarifa = tarifa_envio(datos["provincia"], datos["codigo_postal"])
        return Response({"zona": tarifa["zona"], "costo": _pesos(tarifa["costo"])})
