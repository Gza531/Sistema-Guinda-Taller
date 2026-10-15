from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Compra, DetalleCompra, ProveedorXProducto
from stock.models import Stock
from stock import services as stock_services

@transaction.atomic
def crear_compra(
    *,
    proveedor,
    usuario,
    detalles,
    numero_factura=None,
    observaciones=None
):
    if not detalles:
        raise ValidationError({
            "detalles": "La compra debe tener al menos un producto."
        })

    compra = Compra.objects.create(
        proveedor=proveedor,
        usuario=usuario,
        numero_factura=numero_factura,
        observaciones=observaciones,
        total=Decimal("0.00"),
        estado=Compra.EstadoCompra.PENDIENTE,
    )

    total = Decimal("0.00")

    for detalle in detalles:
        producto = detalle["producto"]
        cantidad = detalle["cantidad"]
        precio_unitario = detalle["precio_unitario"]

        existe_relacion = ProveedorXProducto.objects.filter(
            proveedor=proveedor,
            producto=producto
        ).exists()

        if not existe_relacion:
            raise ValidationError({
                "producto": f"El proveedor no tiene asociado el producto {producto}."
            })

        subtotal = Decimal(str(precio_unitario)) * cantidad

        DetalleCompra.objects.create(
            compra=compra,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            subtotal=subtotal,
        )

        total += subtotal

    compra.total = total
    compra.save(update_fields=["total"])

    return compra

@transaction.atomic
def recibir_compra(*, compra, usuario):
    compra = Compra.objects.select_for_update().get(
        pk=compra.pk
    )

    if compra.estado == Compra.EstadoCompra.RECIBIDA:
        raise ValidationError({
            "estado": "La compra ya fue recibida."
        })

    if compra.estado == Compra.EstadoCompra.ANULADA:
        raise ValidationError({
            "estado": "No se puede recibir una compra anulada."
        })

    detalles = DetalleCompra.objects.select_related("producto").filter(
        compra=compra
    )

    if not detalles.exists():
        raise ValidationError({
            "detalles": "La compra no tiene productos cargados."
        })

    for detalle in detalles:
        stock_services.registrar_entrada(
            producto=detalle.producto,
            ubicacion=Stock.Ubicaciones.DEPOSITO,
            cantidad=detalle.cantidad,
            usuario=usuario,
            motivo=f"Recepción de compra {compra.id_compra}",
        )

    compra.estado = Compra.EstadoCompra.RECIBIDA
    compra.save(update_fields=["estado"])

    return compra
@transaction.atomic
def anular_compra(*, compra):
    compra = Compra.objects.select_for_update().get(
        pk=compra.pk
    )

    if compra.estado == Compra.EstadoCompra.RECIBIDA:
        raise ValidationError({
            "estado": "No se puede anular una compra ya recibida."
        })

    if compra.estado == Compra.EstadoCompra.ANULADA:
        raise ValidationError({
            "estado": "La compra ya está anulada."
        })

    compra.estado = Compra.EstadoCompra.ANULADA
    compra.save(update_fields=["estado"])

    return compra