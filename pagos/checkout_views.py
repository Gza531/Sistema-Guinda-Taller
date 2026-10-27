import os
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from clientes.models import Cliente
from ventas.services import (
    DEPOSITO,
    Entrega,
    _agrupar,
    _armar_lineas,
    _verificar_stock,
)

from .checkout_serializers import CheckoutSerializer
from .services import ErrorMercadoPago, crear_preferencia


class PagoNoDisponible(APIException):
    status_code = 503
    default_detail = "No se pudo iniciar el pago. Intentá nuevamente."
    default_code = "pago_no_disponible"


class CheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        entrada = CheckoutSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        # El cliente sale del usuario autenticado.
        cliente = Cliente.objects.filter(
            usuario=request.user,
            estado=True,
        ).first()

        if cliente is None or cliente.es_consumidor_final:
            raise PermissionDenied(
                "Necesitás un cliente activo asociado a tu usuario."
            )

        # Reutilizamos las reglas de Ventas.
        cantidades = _agrupar(datos["items"])
        _verificar_stock(cantidades, DEPOSITO)
        lineas = _armar_lineas(cantidades)

        entrega = datos["entrega"]
        direccion = ""

        if entrega == Entrega.ENVIO:
            direccion = (
                datos.get("direccion_entrega")
                or cliente.direccion
                or ""
            ).strip()

            if not direccion:
                raise ValidationError({
                    "direccion_entrega": "Indicá una dirección de entrega."
                })

        # El costo se configura en el servidor, no en React.
        try:
            costo_configurado = Decimal(
                os.environ.get("MP_COSTO_ENVIO", "0") or "0"
            )
        except InvalidOperation as error:
            raise PagoNoDisponible() from error

        if (
            not costo_configurado.is_finite()
            or costo_configurado < 0
        ):
            raise PagoNoDisponible()

        costo_envio = (
            costo_configurado
            if entrega == Entrega.ENVIO
            else Decimal("0.00")
        )

        total = sum(
            (linea["subtotal"] for linea in lineas),
            Decimal("0.00"),
        ) + costo_envio

        if total <= 0:
            raise ValidationError({
                "items": "El total de la compra debe ser mayor a cero."
            })

        metadata = {
            "cliente_id": cliente.pk,
            "items": [
                {
                    "producto": producto.pk,
                    "cantidad": cantidad,
                }
                for producto, cantidad in cantidades.items()
            ],
            "entrega": entrega,
            "direccion_entrega": direccion,
            "costo_envio": str(costo_envio),
        }

        try:
            preferencia = crear_preferencia(
                cliente=cliente,
                lineas=lineas,
                costo_envio=costo_envio,
                metadata=metadata,
            )
        except (ErrorMercadoPago, ImproperlyConfigured) as error:
            raise PagoNoDisponible() from error

        return Response(
            {
                "id": preferencia["id"],
                "init_point": preferencia["init_point"],
                "total": str(total),
            },
            status=status.HTTP_201_CREATED,
        )