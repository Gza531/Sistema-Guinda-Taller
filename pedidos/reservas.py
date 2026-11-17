"""
Reserva de stock de los pedidos.

Los pedidos se pagan por adelantado (transferencia), así que la mercadería
tiene que quedar apartada desde que se registra el pedido hasta que se entrega.
La reserva no mueve stock: las unidades siguen en el Depósito, pero las de los
pedidos abiertos ya no están disponibles para otras ventas online, otros pedidos
ni traslados al salón.

    disponible en el Depósito = stock del Depósito - unidades en pedidos abiertos

Al entregar el pedido, el stock sale del Depósito como en cualquier venta online
y la reserva desaparece (el pedido pasa a Entregado). Si se cancela, las unidades
vuelven a estar disponibles solas.
"""

from django.db.models import IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from .models import DetallePedido, Pedido


E = Pedido.EstadoPedido

# Pedidos que todavía no se entregaron ni se cancelaron: apartan sus unidades.
ESTADOS_QUE_RESERVAN = [E.PENDIENTE, E.RESERVADO, E.LISTO]


def _detalles_abiertos(excluir_pedido=None):
    detalles = DetallePedido.objects.filter(pedido__estado__in=ESTADOS_QUE_RESERVAN)
    if excluir_pedido is not None:
        detalles = detalles.exclude(pedido=excluir_pedido)
    return detalles


def reservadas(producto, *, excluir_pedido=None):
    """Unidades de ese producto apartadas en pedidos abiertos."""
    return _detalles_abiertos(excluir_pedido).filter(producto=producto).aggregate(
        total=Coalesce(Sum("cantidad"), 0)
    )["total"]


def subconsulta_reservadas(campo_producto="pk"):
    """
    Para anotar un queryset: unidades reservadas de cada producto, calculadas por la
    base en la misma consulta. campo_producto: "pk" en productos, "producto" en stock.
    """
    por_producto = (
        _detalles_abiertos()
        .filter(producto=OuterRef(campo_producto))
        .values("producto")
        .annotate(total=Sum("cantidad"))
        .values("total")
    )
    return Coalesce(Subquery(por_producto, output_field=IntegerField()), Value(0))
