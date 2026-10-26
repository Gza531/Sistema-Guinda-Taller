
import os
from decimal import Decimal

import mercadopago
from django.core.exceptions import ImproperlyConfigured


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


def _verificar_respuesta(resultado, operacion):
    """
    Comprueba que Mercado Pago haya respondido correctamente.
    """
    codigo = resultado.get("status")
    datos = resultado.get("response")

    if codigo not in (200, 201) or not isinstance(datos, dict):
        raise RuntimeError(
            f"Error de Mercado Pago al {operacion}. HTTP: {codigo}"
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

    resultado = _sdk().preference().create(preferencia)
    datos = _verificar_respuesta(resultado, "crear preferencia")

    return {
        "id": datos["id"],
        "init_point": datos["init_point"],
    }


def obtener_pago(payment_id):
    """
    Consulta los datos de un pago en Mercado Pago.

    Gonza utilizará esta función desde el webhook.
    """
    resultado = _sdk().payment().get(payment_id)

    return _verificar_respuesta(resultado, "consultar pago")


def reembolsar(payment_id):
    """
    Solicita la devolución total de un pago.

    Gonza utilizará esta función cuando corresponda
    devolver el dinero de una venta.
    """
    resultado = _sdk().refund().create(payment_id)

    return _verificar_respuesta(resultado, "reembolsar pago")
