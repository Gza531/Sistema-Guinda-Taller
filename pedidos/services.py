"""
Reglas de negocio para el módulo de Pedidos.

Crear o modificar un pedido no mueve stock ni caja.
Esas operaciones se realizarán al entregar el pedido.
"""

from collections import OrderedDict

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import DetallePedido, Pedido
from promociones.services import precio_con_descuento
from ventas.services import registrar_venta_online


E = Pedido.EstadoPedido

# Estados permitidos para cambios manuales.
TRANSICIONES = {
    E.PENDIENTE: {E.RESERVADO, E.EN_ESPERA_STOCK},
    E.RESERVADO: {E.LISTO},
    E.EN_ESPERA_STOCK: {E.LISTO},
    E.LISTO: set(),
}

# Estados desde los que se permite cancelar.
CANCELABLES = {
    E.PENDIENTE,
    E.RESERVADO,
    E.EN_ESPERA_STOCK,
    E.LISTO,
}

@transaction.atomic
def crear_pedido(*, cliente, canal, items, usuario, observaciones=None):

    if not items:
        raise ValidationError({
            "items": "El pedido debe tener al menos un producto."
        })

    if not cliente.estado:
        raise ValidationError({
            "cliente": f"El cliente «{cliente}» está dado de baja."
        })

    if cliente.es_consumidor_final:
        raise ValidationError({
            "cliente": (
                "Un pedido necesita un cliente identificado "
                "para poder avisarle. Cárguelo primero en Clientes."
            )
        })

    productos = OrderedDict()

    for item in items:
        producto = item["producto"]
        cantidad = item["cantidad"]

        if producto not in productos:
            productos[producto] = 0

        productos[producto] += cantidad

    pedido = Pedido.objects.create(
        cliente=cliente,
        canal=canal,
        usuario=usuario,
        observaciones=observaciones
    )

    detalles = [
        DetallePedido(
            pedido=pedido,
            producto=producto,
            cantidad=cantidad,
            precio_referencia=precio_con_descuento(producto)
        )
        for producto, cantidad in productos.items()
    ]

    DetallePedido.objects.bulk_create(detalles)
    return pedido

@transaction.atomic
def cambiar_estado(*, pedido, estado):
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)   

    if estado == E.CANCELADO:
        raise ValidationError({
            "estado": "Para cancelar, use /cancelar/."
        })

    if estado == E.ENTREGADO:
        raise ValidationError({
            "estado": "Un pedido se entrega con /entregar/."
        })

    permitidos = TRANSICIONES.get(pedido.estado, set())

    if estado not in permitidos:
        if not permitidos:
            mensaje = (
                f"Un pedido {pedido.get_estado_display()} "
                "ya no cambia de estado."
            )
        else:
            destinos = ", ".join(
                E(valor).label for valor in sorted(permitidos)
            )
            mensaje = (
                f"Un pedido {pedido.get_estado_display()} "
                f"solo puede pasar a: {destinos}."
            )

        raise ValidationError({"estado": mensaje})

    pedido.estado = estado
    pedido.save(update_fields=["estado"])

    return pedido   

@transaction.atomic
def cancelar_pedido(*, pedido, motivo):
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)

    if pedido.estado not in CANCELABLES:
        raise ValidationError({
            "estado": (
                f"Un pedido {pedido.get_estado_display()} "
                "ya no se puede cancelar. Solo se cancelan "
                "los pedidos Pendientes, Reservados, En espera de stock o Listos."
            )
        })

    motivo = (motivo or "").strip()

    if not motivo:
        raise ValidationError({
            "motivo": "Debe indicar un motivo de cancelación."
        })

    if pedido.observaciones:
        observaciones = (
            f"{pedido.observaciones} | Cancelado: {motivo}"
        )
    else:
        observaciones = f"Cancelado: {motivo}"

    if len(observaciones) > 500:
        raise ValidationError({
            "motivo": "Las observaciones no pueden superar los 500 caracteres."
        })

    pedido.estado = E.CANCELADO
    pedido.observaciones = observaciones

    pedido.save(update_fields=["estado", "observaciones"])

    return pedido


@transaction.atomic
def entregar_pedido(
    *,
    pedido,
    usuario,
    pagos,
    entrega,
    direccion_entrega=None,
    costo_envio=None
):
    """
    Concreta un pedido creando una venta online asociada.

    - Solo se puede entregar un pedido Listo.
    - Cada pedido puede generar como máximo una venta.
    - Se respetan los precios originales del pedido.
    - El stock sale del Depósito.
    - Si algo falla, se deshace toda la operación.
    """

    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)

    if pedido.estado != E.LISTO:
        raise ValidationError({
            "estado": (
                f"Solo se entrega un pedido Listo. "
                f"Este está {pedido.get_estado_display()}."
            )
        })

    if pedido.venta_set.exists():
        raise ValidationError({
            "estado": "Este pedido ya tiene una venta."
        })

    detalles = list(
        pedido.detallepedido_set.select_related("producto")
    )

    items = [
        {
            "producto": d.producto,
            "cantidad": d.cantidad
        }
        for d in detalles
    ]

    precios = {
        d.producto_id: d.precio_referencia
        for d in detalles
    }

    registrar_venta_online(
        usuario=usuario,
        cliente=pedido.cliente,
        items=items,
        pagos=pagos,
        entrega=entrega,
        direccion_entrega=direccion_entrega,
        costo_envio=costo_envio,
        observaciones=f"Pedido {pedido.pk}",
        precios=precios,
        pedido=pedido,
    )

    pedido.estado = E.ENTREGADO
    pedido.save(update_fields=["estado"])

    return pedido
