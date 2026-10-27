"""
Qué hace el sistema cuando Mercado Pago avisa un pago (webhook).

1. Consulta el pago real a la API (nunca se confía en el aviso: solo trae el ID).
2. Si ese pago ya registró una venta, no hace nada (idempotencia: Mercado Pago
   puede avisar el mismo pago más de una vez).
3. Si el pago no está aprobado (pendiente, rechazado, devuelto), no hace nada.
4. Si está aprobado, registra la venta online con los datos que el checkout
   guardó en la metadata: stock del Depósito, envío si corresponde y cobro en la
   caja online con el método «Mercado Pago».
5. Si la venta no se puede registrar (sin stock, cambió un precio y el total ya no
   coincide, cliente dado de baja...), devuelve el dinero completo.

Los errores de comunicación con Mercado Pago (ErrorMercadoPago) NO se atrapan acá:
la vista responde 500 y Mercado Pago reintenta más tarde.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError
from rest_framework.exceptions import ValidationError

from cajas.models import MetodoPago
from catalogo.models import Producto
from clientes.models import Cliente
from ventas.models import Venta
from ventas.services import Entrega, registrar_venta_online

from .services import obtener_pago, reembolsar


logger = logging.getLogger(__name__)

APROBADO = "approved"

# Resultados posibles (los devuelve la vista y quedan en el log)
REGISTRADA = "venta_registrada"
YA_REGISTRADA = "ya_registrada"
IGNORADO = "ignorado"
REEMBOLSADO = "reembolsado"


def _datos_de_la_venta(pago):
    """
    Arma los argumentos de registrar_venta_online a partir de la metadata
    que guardó el checkout (E2) y del monto que realmente se cobró.
    """
    meta = pago.get("metadata") or {}

    try:
        cliente = Cliente.objects.select_related("usuario").get(
            pk=int(meta["cliente"]), estado=True
        )
        items = [
            {
                "producto": Producto.objects.get(pk=int(item["producto"])),
                "cantidad": int(item["cantidad"]),
            }
            for item in meta["items"]
        ]
        entrega = meta["entrega"]
        costo_envio = Decimal(str(meta.get("costo_envio") or "0"))
        monto = Decimal(str(pago["transaction_amount"])).quantize(Decimal("0.01"))
    except (KeyError, TypeError, ValueError, InvalidOperation,
            Cliente.DoesNotExist, Producto.DoesNotExist) as error:
        raise ValidationError({"metadata": f"Datos del pago incompletos o inválidos ({error})."})

    if cliente.usuario is None:
        raise ValidationError({"cliente": "El cliente no tiene usuario asociado."})

    es_envio = entrega == Entrega.ENVIO

    return {
        # Una compra web no la registra un empleado: queda a nombre del usuario del cliente.
        "usuario": cliente.usuario,
        "cliente": cliente,
        "items": items,
        "pagos": [{"metodo_pago": MetodoPago.mercado_pago(), "monto": monto}],
        "entrega": entrega,
        "direccion_entrega": meta.get("direccion_entrega") if es_envio else None,
        "costo_envio": costo_envio if es_envio else None,
    }


def procesar_pago(payment_id):
    pago = obtener_pago(payment_id)
    mp_id = str(pago["id"])

    # G4 — Idempotencia: el mismo pago avisado dos veces no registra dos ventas.
    if Venta.objects.filter(mp_payment_id=mp_id).exists():
        return YA_REGISTRADA

    if pago.get("status") != APROBADO:
        return IGNORADO

    try:
        datos = _datos_de_la_venta(pago)
        registrar_venta_online(
            **datos,
            observaciones=f"Tienda web · pago Mercado Pago {mp_id}",
            mp_payment_id=mp_id,
        )

    except IntegrityError:
        # Dos avisos del mismo pago llegaron a la vez: el otro ya registró la venta
        # (lo garantiza el unique de mp_payment_id). No se devuelve nada.
        if Venta.objects.filter(mp_payment_id=mp_id).exists():
            return YA_REGISTRADA
        raise

    except ValidationError as error:
        # G5 — Pagó pero la venta no se puede registrar: se le devuelve el dinero.
        logger.warning(
            "Pago %s aprobado pero no se pudo registrar la venta (%s). Se devuelve el dinero.",
            mp_id, error.detail,
        )
        reembolsar(mp_id)
        return REEMBOLSADO

    return REGISTRADA
