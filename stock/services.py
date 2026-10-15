from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import MovimientoStock, Stock


def _obtener_stock(producto, ubicacion, crear=False):
    """Busca el stock de un producto en una ubicación y lo bloquea mientras dura la operación."""
    try:
        return Stock.objects.select_for_update().get(producto=producto, ubicacion=ubicacion)
    except Stock.DoesNotExist:
        if crear:
            return Stock.objects.create(producto=producto, ubicacion=ubicacion)
        raise ValidationError(
            {"producto": f"No hay stock registrado de «{producto}» en {ubicacion}."}
        )


@transaction.atomic
def registrar_entrada(*, producto, ubicacion, cantidad, usuario, motivo=None,
                      compra=None, venta=None):
    """Suma unidades. Si el producto no tenía stock en esa ubicación, lo crea."""
    stock = _obtener_stock(producto, ubicacion, crear=True)

    stock.cantidad_actual = stock.cantidad_actual + cantidad
    stock.save()

    return MovimientoStock.objects.create(
        stock=stock,
        tipo_movimiento=MovimientoStock.Movimientos.ENTRADA,
        cantidad=cantidad,
        usuario=usuario,
        motivo=motivo,
        compra=compra,
        venta=venta,
    )


@transaction.atomic
def registrar_salida(*, producto, ubicacion, cantidad, usuario, motivo=None, venta=None):
    """Resta unidades. No permite que el stock quede negativo."""
    stock = _obtener_stock(producto, ubicacion)

    if cantidad > stock.cantidad_actual:
        raise ValidationError(
            {"cantidad": f"Stock insuficiente: hay {stock.cantidad_actual} y se pidieron {cantidad}."}
        )

    stock.cantidad_actual = stock.cantidad_actual - cantidad
    stock.save()

    return MovimientoStock.objects.create(
        stock=stock,
        tipo_movimiento=MovimientoStock.Movimientos.SALIDA,
        cantidad=cantidad,
        usuario=usuario,
        motivo=motivo,
        venta=venta
    )

@transaction.atomic
def registrar_reposicion(*, producto, origen, cantidad, usuario, motivo=None):
    """Traslada mercadería entre el Depósito y el salón (Sucursal), en cualquier sentido."""
    # Siempre se bloquea primero el depósito y después el salón,
    # así dos traslados simultáneos en sentidos opuestos no se traban entre sí.
    deposito = _obtener_stock(producto, Stock.Ubicaciones.DEPOSITO, crear=True)
    salon = _obtener_stock(producto, Stock.Ubicaciones.SUCURSAL, crear=True)

    if origen == Stock.Ubicaciones.DEPOSITO:
        desde, hacia = deposito, salon
    else:
        desde, hacia = salon, deposito

    if cantidad > desde.cantidad_actual:
        raise ValidationError(
            {"cantidad": f"En {desde.ubicacion} hay {desde.cantidad_actual} unidades, no alcanza para trasladar {cantidad}."}
        )

    desde.cantidad_actual = desde.cantidad_actual - cantidad
    desde.save()

    hacia.cantidad_actual = hacia.cantidad_actual + cantidad
    hacia.save()

    tipo = MovimientoStock.Movimientos.REPOSICION

    sale = MovimientoStock.objects.create(
        stock=desde, tipo_movimiento=tipo, cantidad=cantidad,
        usuario=usuario, motivo=motivo or f"Traslado: sale de {desde.ubicacion}",
    )
    entra = MovimientoStock.objects.create(
        stock=hacia, tipo_movimiento=tipo, cantidad=cantidad,
        usuario=usuario, motivo=motivo or f"Traslado: entra a {hacia.ubicacion}",
    )

    return [sale, entra]