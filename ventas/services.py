"""
Reglas de negocio del módulo Ventas (DFD: Gestionar Venta Presencial).
"""
import uuid
from collections import OrderedDict
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from cajas.models import Caja, MovimientoCaja
from cajas.services import registrar_movimiento_caja, sesion_abierta
from clientes.models import Cliente
from stock.models import Stock
from stock.services import registrar_entrada, registrar_salida

from .models import DetalleVenta, Venta

from promociones.services import descuento_vigente

def _stock_en(producto, ubicacion):
    fila = Stock.objects.filter(producto=producto, ubicacion=ubicacion).first()
    return fila.cantidad_actual if fila else 0


@transaction.atomic
def registrar_venta_presencial(*, usuario, caja, items, pagos, cliente=None, observaciones=None):
    """
    Registra una venta en el local, en una sola transacción: o se guarda todo, o nada.
    items: [{"producto": Producto, "cantidad": int}, ...]
    pagos: [{"metodo_pago": MetodoPago, "monto": Decimal}, ...]

    RN-02: toda venta tiene al menos un producto.
    RN-03: sin cliente identificado, se registra a nombre de «Consumidor Final».
    RN-04: la venta presencial descuenta stock de la Sucursal (salón).
    RN-05: se descuenta el stock con un movimiento de salida asociado a la venta.
    RN-06: el precio se copia al detalle en el momento de vender.
    RN-07: subtotales y total los calcula el sistema.
    RN-08: los pagos (uno o varios métodos) tienen que sumar exactamente el total.
    RN-09: la venta presencial exige una caja presencial abierta.
    """
    # ---- 1. Validaciones previas: si algo está mal, no se escribe nada ----
    if caja.tipo_caja != Caja.TipoCaja.PRESENCIAL:
        raise ValidationError({"caja": f"«{caja}» no es una caja presencial."})
    if sesion_abierta(caja) is None:
        raise ValidationError({"caja": f"La caja «{caja}» está cerrada. Ábrala para vender."})

    if not items:
        raise ValidationError({"items": "La venta tiene que tener al menos un producto."})

    # Si el mismo producto viene dos veces, se suman las cantidades
    cantidades = OrderedDict()
    for item in items:
        producto = item["producto"]
        cantidades[producto] = cantidades.get(producto, 0) + item["cantidad"]

    salon = Stock.Ubicaciones.SUCURSAL
    faltantes = []
    for producto, cantidad in cantidades.items():
        hay = _stock_en(producto, salon)
        if cantidad > hay:
            en_deposito = _stock_en(producto, Stock.Ubicaciones.DEPOSITO)
            aviso = f" (en el depósito hay {en_deposito}: haga un traslado)" if en_deposito else ""
            faltantes.append(f"«{producto}»: hay {hay} en el salón y se piden {cantidad}{aviso}.")
    if faltantes:
        raise ValidationError({"items": faltantes})

    # Promociones: cada producto lleva la promoción vigente con mayor descuento.
    # El precio de lista y el descuento quedan copiados en el detalle (RN-06).
    lineas = []
    for producto, cantidad in cantidades.items():
        _, descuento_unitario = descuento_vigente(producto)
        lineas.append({
            "producto": producto,
            "cantidad": cantidad,
            "precio_unitario": producto.precio_venta,
            "descuento_aplicado": descuento_unitario * cantidad,
            "subtotal": (producto.precio_venta - descuento_unitario) * cantidad,
        })

    total = sum((linea["subtotal"] for linea in lineas), Decimal("0.00"))
    pagado = sum((p["monto"] for p in pagos), Decimal("0.00"))
    if pagado != total:
        raise ValidationError({
            "pagos": f"Los pagos suman ${pagado} y el total de la venta es ${total}."
        })

    # ---- 2. Venta y detalles ----
    venta = Venta.objects.create(
        tipo=Venta.TipoVenta.PRESENCIAL,
        cliente=cliente or Cliente.consumidor_final(),
        usuario=usuario,
        total=total,
        observaciones=observaciones,
        numero_comprobante=uuid.uuid4().hex[:20],  # provisorio, se reemplaza abajo
    )
    venta.numero_comprobante = f"V-{venta.pk:08d}"
    venta.save(update_fields=["numero_comprobante"])

    for linea in lineas:
        DetalleVenta.objects.create(venta=venta, **linea)
        # ---- 3. Stock: sale del salón, vinculado a la venta ----
        registrar_salida(
            producto=linea["producto"],
            ubicacion=salon,
            cantidad=linea["cantidad"],
            usuario=usuario,
            motivo=f"Venta {venta.numero_comprobante}",
            venta=venta,
        )

    # ---- 4. Cobro: un movimiento de caja por cada pago ----
    for pago in pagos:
        registrar_movimiento_caja(
            caja=caja,
            tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO,
            monto=pago["monto"],
            metodo_pago=pago["metodo_pago"],
            concepto=f"Cobro venta {venta.numero_comprobante}",
            venta=venta,
        )

    return venta

@transaction.atomic
def anular_venta(*, venta, usuario, motivo):
    """
    Anula una venta: la venta no se borra, queda en estado ANULADA (RIR, política general punto 5).
    RN-13: se devuelve el stock con un movimiento de entrada y se registra el egreso en caja.
    El dinero se devuelve por el mismo método con que se cobró, desde la misma caja,
    que tiene que estar abierta en este momento.
    """
    venta = Venta.objects.select_for_update().get(pk=venta.pk)

    if venta.estado == Venta.EstadoVenta.ANULADA:
        raise ValidationError({"estado": f"La venta {venta.numero_comprobante} ya está anulada."})

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Indique el motivo de la anulación."})

    cobros = list(
        MovimientoCaja.objects
        .filter(venta=venta, tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO)
        .select_related("apertura_cierre__caja", "metodo_pago")
    )
    for cobro in cobros:
        caja = cobro.apertura_cierre.caja
        if sesion_abierta(caja) is None:
            raise ValidationError({"caja": f"La caja «{caja}» está cerrada. Ábrala para registrar la devolución."})

    texto = f"Anulada: {motivo}"
    if venta.observaciones:
        texto = f"{venta.observaciones} | {texto}"
    if len(texto) > 500:
        raise ValidationError({"motivo": "El motivo es demasiado largo."})

    # Stock: vuelve al salón, vinculado a la venta
    for detalle in venta.detalleventa_set.select_related("producto"):
        registrar_entrada(
            producto=detalle.producto,
            ubicacion=Stock.Ubicaciones.SUCURSAL,
            cantidad=detalle.cantidad,
            usuario=usuario,
            motivo=f"Anulación venta {venta.numero_comprobante}",
            venta=venta,
        )

    # Caja: un egreso por cada cobro, por el mismo método y monto
    for cobro in cobros:
        registrar_movimiento_caja(
            caja=cobro.apertura_cierre.caja,
            tipo_movimiento=MovimientoCaja.TipoMovimiento.EGRESO,
            monto=cobro.monto,
            metodo_pago=cobro.metodo_pago,
            concepto=f"Devolución por anulación de venta {venta.numero_comprobante}",
            venta=venta,
        )

    venta.estado = Venta.EstadoVenta.ANULADA
    venta.observaciones = texto
    venta.save(update_fields=["estado", "observaciones"])
    return venta