import logging
import os

from mercadopago.webhook import InvalidWebhookSignatureError, WebhookSignatureValidator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .webhook_services import procesar_pago


logger = logging.getLogger(__name__)


class WebhookMercadoPagoAPIView(APIView):
    """
    POST /api/pagos/webhook/?data.id=<id del pago>&type=payment

    Lo llama Mercado Pago, no un usuario: no lleva login ni CSRF.
    La seguridad es la firma (header x-signature), que se valida con MP_WEBHOOK_SECRET.

    Respuestas:
      200 → recibido (Mercado Pago no vuelve a avisar)
      401 → firma inválida
      500 → error temporal (Mercado Pago reintenta más tarde)
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        datos = request.data if isinstance(request.data, dict) else {}
        tipo = request.query_params.get("type") or datos.get("type")
        data_id = request.query_params.get("data.id") or (datos.get("data") or {}).get("id")

        # Solo nos interesan los avisos de pagos; el resto se confirma y se ignora.
        if tipo != "payment" or not data_id:
            return Response({"resultado": "ignorado"}, status=status.HTTP_200_OK)

        secreto = os.environ.get("MP_WEBHOOK_SECRET", "").strip()
        if not secreto:
            logger.error("Falta configurar MP_WEBHOOK_SECRET: no se puede validar el aviso.")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            WebhookSignatureValidator.validate(
                request.headers.get("x-signature"),
                request.headers.get("x-request-id"),
                data_id,
                secreto,
            )
        except InvalidWebhookSignatureError as error:
            logger.warning("Aviso de Mercado Pago rechazado: firma inválida (%s).", error.reason.value)
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            resultado = procesar_pago(data_id)
        except Exception:
            logger.exception("Error al procesar el pago %s de Mercado Pago.", data_id)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info("Pago %s de Mercado Pago: %s.", data_id, resultado)
        return Response({"resultado": resultado}, status=status.HTTP_200_OK)
