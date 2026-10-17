from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from cajas.models import AperturaCierreCaja
from cajas.services import resumen_sesion
from stock.models import Stock
from ventas.models import Venta

CERO = Decimal("0.00")


def ventas_del_dia(fecha=None):
    """Cantidad y total de las ventas de un día (hoy si no se indica), sin contar las anuladas."""
    fecha = fecha or timezone.localdate()

    Estado = Venta.EstadoVenta
    Tipo = Venta.TipoVenta

    validas = Q(estado=Estado.REGISTRADA)
    presenciales = validas & Q(tipo=Tipo.PRESENCIAL)
    online = validas & Q(tipo=Tipo.ONLINE)

    # Los nombres van como "importe" y no "total" porque Django no deja
    # que el resultado de un Sum se llame igual que un campo del modelo.
    datos = Venta.objects.filter(fecha__date=fecha).aggregate(
        cantidad=Count("pk", filter=validas),
        importe=Sum("total", filter=validas, default=CERO),
        presencial_cantidad=Count("pk", filter=presenciales),
        presencial_importe=Sum("total", filter=presenciales, default=CERO),
        online_cantidad=Count("pk", filter=online),
        online_importe=Sum("total", filter=online, default=CERO),
        anuladas=Count("pk", filter=Q(estado=Estado.ANULADA)),
    )

    return {
        "fecha": fecha,
        "cantidad": datos["cantidad"],
        "total": datos["importe"],
        "presencial": {
            "cantidad": datos["presencial_cantidad"],
            "total": datos["presencial_importe"],
        },
        "online": {
            "cantidad": datos["online_cantidad"],
            "total": datos["online_importe"],
        },
        "anuladas": datos["anuladas"],
    }


def stock_bajo_minimo():
    """Existencias de productos activos que están en el mínimo o por debajo."""
    existencias = (
        Stock.objects
        .filter(cantidad_actual__lte=F("stock_minimo"), producto__estado=True)
        .select_related("producto")
        .order_by("producto__nombre", "ubicacion")
    )

    return [
        {
            "id_producto": s.producto.id_producto,
            "producto": s.producto.nombre,
            "ubicacion": s.get_ubicacion_display(),
            "cantidad_actual": s.cantidad_actual,
            "stock_minimo": s.stock_minimo,
            "faltante": s.stock_minimo - s.cantidad_actual,
        }
        for s in existencias
    ]


def cajas_abiertas():
    """Sesiones de caja abiertas ahora, con el efectivo que debería haber en cada una."""
    sesiones = (
        AperturaCierreCaja.objects
        .filter(fecha_cierre__isnull=True)
        .select_related("caja", "usuario")
        .order_by("fecha_apertura")
    )

    return [
        {
            "id_caja": sesion.caja.id_caja,
            "caja": sesion.caja.nombre,
            "tipo_caja": sesion.caja.tipo_caja,
            "id_sesion": sesion.id_apertura_cierre,
            "abierta_desde": sesion.fecha_apertura,
            "abierta_por": sesion.usuario.username if sesion.usuario else None,
            "efectivo_esperado": resumen_sesion(sesion)["efectivo_esperado"],
        }
        for sesion in sesiones
    ]


def resumen():
    """Todo lo que muestra el dashboard, en un solo diccionario."""
    return {
        "ventas_hoy": ventas_del_dia(),
        "stock_bajo_minimo": stock_bajo_minimo(),
        "cajas_abiertas": cajas_abiertas(),
    }