"""
Servicios del módulo Promociones.

Calcula descuentos y administra promociones.
No registra ventas ni modifica pedidos existentes.

Ventas y Pedidos copian el precio al momento de la operación,
por lo que cambios posteriores en una promoción no afectan
los precios ya registrados.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Promocion, PromocionProducto


CERO = Decimal("0.00")
T = Promocion.TipoDescuento

def vigentes(fecha=None):
    """
    Devuelve las promociones activas cuya fecha actual
    está dentro del período de vigencia.
    """
    fecha = fecha or timezone.localdate()

    return Promocion.objects.filter(
        estado=True,
        fecha_inicio__lte=fecha,
        fecha_fin__gte=fecha
    )

def monto_descuento(promocion, precio):
    """
    Calcula el descuento por unidad.
    Nunca devuelve un descuento mayor que el precio.
    """
    if promocion.tipo_descuento == T.PORCENTAJE:
        monto = (
            precio * promocion.valor_descuento / Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    else:
        monto = promocion.valor_descuento

    return min(monto, precio)

def descuento_vigente(producto, fecha=None):
    """
    Devuelve la promoción con mayor descuento para un producto.

    Si no hay promociones vigentes, devuelve (None, 0).
    """
    mejor, monto_mejor = None, CERO

    for promo in vigentes(fecha).filter(
        promocionproducto__producto=producto
    ):
        monto = monto_descuento(promo, producto.precio_venta)

        if monto > monto_mejor:
            mejor, monto_mejor = promo, monto

    return mejor, monto_mejor

def precio_con_descuento(producto, fecha=None):
    _, monto = descuento_vigente(producto, fecha)
    return producto.precio_venta - monto

def _validar(*, tipo_descuento, valor_descuento,
            fecha_inicio, fecha_fin, productos):

    errores = {}

    if fecha_fin < fecha_inicio:
        errores["fecha_fin"] = (
            "La fecha de fin no puede ser anterior a la de inicio."
        )

    if valor_descuento <= 0:
        errores["valor_descuento"] = (
            "El descuento tiene que ser mayor que cero."
        )

    elif tipo_descuento == T.PORCENTAJE and valor_descuento > 100:
        errores["valor_descuento"] = (
            "Un porcentaje va de 1 a 100."
        )

    if not productos:
        errores["productos"] = (
            "La promoción tiene que alcanzar al menos un producto."
        )

    if tipo_descuento == T.MONTO_FIJO and productos:
        invalidos = [
            f'"{p.nombre}" (${p.precio_venta})'
            for p in productos
            if valor_descuento >= p.precio_venta
        ]

        if invalidos:
            errores["valor_descuento"] = (
                f"Un descuento fijo de ${valor_descuento} "
                f"tiene que ser menor que el precio de: "
                f"{', '.join(invalidos)}."
            )

    if errores:
        raise ValidationError(errores)

def _sin_repetir(productos):
    """
    Elimina productos duplicados manteniendo
    el orden en el que fueron recibidos.
    """
    unicos = {}

    for producto in productos:
        unicos.setdefault(producto.pk, producto)

    return list(unicos.values())

@transaction.atomic
def crear_promocion(*, productos, **datos):
    """
    Crea una promoción y la asocia con sus productos.
    """

    productos = _sin_repetir(productos)

    _validar(
        tipo_descuento=datos["tipo_descuento"],
        valor_descuento=datos["valor_descuento"],
        fecha_inicio=datos["fecha_inicio"],
        fecha_fin=datos["fecha_fin"],
        productos=productos
    )

    promocion = Promocion.objects.create(**datos)

    PromocionProducto.objects.bulk_create([
        PromocionProducto(
            promocion=promocion,
            producto=producto
        )
        for producto in productos
    ])

    return promocion

@transaction.atomic
def actualizar_promocion(*, promocion, productos=None, **datos):
    """
    Actualiza una promoción existente.
    Permite modificar todos los campos o solo algunos.
    """

    promocion = Promocion.objects.select_for_update().get(
        pk=promocion.pk
    )

    for campo, valor in datos.items():
        setattr(promocion, campo, valor)

    if productos is None:
        productos_validar = [
            relacion.producto
            for relacion in promocion.promocionproducto_set
                .select_related("producto").all()
        ]
    else:
        productos = _sin_repetir(productos)
        productos_validar = productos

    _validar(
        tipo_descuento=promocion.tipo_descuento,
        valor_descuento=promocion.valor_descuento,
        fecha_inicio=promocion.fecha_inicio,
        fecha_fin=promocion.fecha_fin,
        productos=productos_validar
    )

    promocion.save()

    if productos is not None:
        PromocionProducto.objects.filter(
            promocion=promocion
        ).delete()

        PromocionProducto.objects.bulk_create([
            PromocionProducto(
                promocion=promocion,
                producto=producto
            )
            for producto in productos
        ])

    return promocion