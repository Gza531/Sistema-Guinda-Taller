
import os
from decimal import Decimal

import mercadopago
import requests
from mercadopago.config import RequestOptions
from django.core.exceptions import ImproperlyConfigured

from mercadopago.errors.exceptions import MercadoPagoError

class ErrorMercadoPago(Exception):
    """
    Error al comunicarse con Mercado Pago
    o al procesar una respuesta de su API.
    """
    pass

def _sdk():
    """
    Crea el cliente de Mercado Pago usando el Access Token
    configurado en las variables de entorno.
    """
    token = os.environ.get("MP_ACCESS_TOKEN", "").strip()

    if not token:
        raise ImproperlyConfigured(
            "Falta configurar MP_ACCESS_TOKEN."
        )

    return mercadopago.SDK(token)


def _llamar(operacion, funcion, *args, **kwargs):
    """
    Ejecuta una operación de Mercado Pago y controla
    los errores de conexión y las respuestas de la API.
    """
    try:
        resultado = funcion(*args, **kwargs)
    except requests.RequestException as e:
        raise ErrorMercadoPago(
            f"No se pudo conectar con Mercado Pago al {operacion}."
        ) from e
    except MercadoPagoError as e:
        raise ErrorMercadoPago(
            f"Error del SDK de Mercado Pago al {operacion}: {e}"
        ) from e

    codigo = resultado.get("status")
    datos = resultado.get("response")

    if codigo not in (200, 201) or not isinstance(datos, dict):
        detalle = datos.get("message", "") if isinstance(datos, dict) else ""

        raise ErrorMercadoPago(
            f"Error de Mercado Pago al {operacion} "
            f"(HTTP {codigo}): {detalle}"
        )

    return datos


def crear_preferencia(*, cliente, lineas, costo_envio, metadata):
    """
    Crea una preferencia de Checkout Pro.

    Devuelve el ID de la preferencia y la URL para pagar.
    """
    items = []

    for linea in lineas:
        cantidad = int(linea["cantidad"])
        subtotal = Decimal(str(linea["subtotal"]))

        items.append({
            "title": str(linea["producto"]),
            "quantity": cantidad,
            "unit_price": float(subtotal / cantidad),
            "currency_id": "ARS",
        })

    costo = Decimal(str(costo_envio or 0))

    if costo > 0:
        items.append({
            "title": "Costo de envío",
            "quantity": 1,
            "unit_price": float(costo),
            "currency_id": "ARS",
        })

    preferencia = {
        "items": items,
        "metadata": metadata,
    }

    datos = _llamar(
        "crear preferencia",
        _sdk().preference().create,
        preferencia,
    )

    return {
        "id": datos["id"],
        "init_point": datos["init_point"],
    }


def obtener_pago(payment_id):
    """
    Consulta los datos de un pago en Mercado Pago.

    Gonza utilizará esta función desde el webhook.
    """
    return _llamar(
        "consultar pago",
        _sdk().payment().get,
        payment_id,
    )


def reembolsar(payment_id):
    """
    Solicita la devolución total de un pago.

    Utiliza una clave de idempotencia para evitar
    solicitudes de devolución duplicadas.
    """
    opciones = RequestOptions(
        custom_headers={
            "x-idempotency-key": f"reembolso-{payment_id}"
        }
    )

    return _llamar(
        "reembolsar pago",
        _sdk().refund().create,
        payment_id,
        request_options=opciones,
    )
