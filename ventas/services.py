"""
Reglas de negocio del módulo Ventas (DFD 1.0 Venta Presencial y 2.0 Venta Online).
"""
import uuid
from collections import OrderedDict
from decimal import Decimal

from django.db import models, transaction
from rest_framework.exceptions import ValidationError

from cajas.models import Caja, MovimientoCaja
from cajas.services import caja_online, registrar_movimiento_caja, sesion_abierta, sesion_online
from clientes.models import Cliente
from envios.services import cancelar_envios_de_venta, crear_envio
from promociones.services import descuento_vigente
from stock.models import Stock
from stock.services import registrar_entrada, registrar_salida

from .models import DetalleVenta, Venta


CERO = Decimal("0.00")
SALON = Stock.Ubicaciones.SUCURSAL
DEPOSITO = Stock.Ubicaciones.DEPOSITO
NOMBRE_UBICACION = {SALON: "el salón", DEPOSITO: "el depósito"}

# La venta presencial descuenta del salón y la online del depósito.
# La anulación devuelve el stock al mismo lugar del que salió.
UBICACION_POR_TIPO = {
    Venta.TipoVenta.PRESENCIAL: SALON,
    Venta.TipoVenta.ONLINE: DEPOSITO,
}


class Entrega(models.TextChoices):
    """Cómo recibe el cliente una venta online."""
    RETIRO = "RETIRO", "Retira en el local"
    ENVIO = "ENVIO", "Envío a domicilio"


# ---------------------------------------------------------------- pasos comunes

def _stock_en(producto, ubicacion):
    fila = Stock.objects.filter(producto=producto, ubicacion=ubicacion).first()
    return fila.cantidad_actual if fila else 0


def _agrupar(items):
    """RN-02: al menos un producto. Si un producto viene dos veces, suma las cantidades."""
    if not items:
        raise ValidationError({"items": "La venta tiene que tener al menos un producto."})

    cantidades = OrderedDict()
    for item in items:
        producto = item["producto"]
        cantidades[producto] = cantidades.get(producto, 0) + item["cantidad"]
    return cantidades


def _verificar_stock(cantidades, ubicacion):
    """Antes de escribir nada, revisa que alcance el stock de la ubicación que corresponde."""
    otra = DEPOSITO if ubicacion == SALON else SALON
    faltantes = []
    for producto, cantidad in cantidades.items():
        hay = _stock_en(producto, ubicacion)
        if cantidad > hay:
            en_otra = _stock_en(producto, otra)
            aviso = f" (en {NOMBRE_UBICACION[otra]} hay {en_otra}: haga un traslado)" if en_otra else ""
            faltantes.append(
                f"«{producto}»: hay {hay} en {NOMBRE_UBICACION[ubicacion]} y se piden {cantidad}{aviso}."
            )
    if faltantes:
        raise ValidationError({"items": faltantes})


def _lineas_con_precios(cantidades, precios):
    """
    Pedidos: el precio ya quedó fijado al crear el pedido,
    incluyendo las promociones de ese momento.

    Se cobra ese precio, sin volver a aplicar promociones.
    """
    return [
        {
            "producto": producto,
            "cantidad": cantidad,
            "precio_unitario": precios[producto.pk],
            "descuento_aplicado": CERO,
            "subtotal": precios[producto.pk] * cantidad,
        }
        for producto, cantidad in cantidades.items()
    ]


def _armar_lineas(cantidades):
    """
    Promociones: cada producto lleva la promoción vigente con mayor descuento.
    El precio de lista y el descuento quedan copiados en el detalle (RN-06).
    """
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
    return lineas


def _validar_pagos(pagos, total):
    """RN-08: los pagos (uno o varios métodos) tienen que sumar exactamente el total."""
    pagado = sum((p["monto"] for p in pagos), CERO)
    if pagado != total:
        raise ValidationError({
            "pagos": f"Los pagos suman ${pagado} y el total de la venta es ${total}."
        })


def _crear_venta(*, tipo, cliente, usuario, total, observaciones, pedido=None):
    venta = Venta.objects.create(
        tipo=tipo,
        pedido=pedido,
        cliente=cliente,
        usuario=usuario,
        total=total,
        observaciones=observaciones,
        numero_comprobante=uuid.uuid4().hex[:20],  # provisorio, se reemplaza abajo
    )
    venta.numero_comprobante = f"V-{venta.pk:08d}"
    venta.save(update_fields=["numero_comprobante"])
    return venta


def _registrar_detalles(*, venta, lineas, ubicacion, usuario):
    """Guarda cada detalle y descuenta el stock con una salida vinculada a la venta (RN-05)."""
    for linea in lineas:
        DetalleVenta.objects.create(venta=venta, **linea)
        registrar_salida(
            producto=linea["producto"],
            ubicacion=ubicacion,
            cantidad=linea["cantidad"],
            usuario=usuario,
            motivo=f"Venta {venta.numero_comprobante}",
            venta=venta,
        )


def _registrar_cobros(*, venta, caja, pagos):
    """Un ingreso de caja por cada pago."""
    for pago in pagos:
        registrar_movimiento_caja(
            caja=caja,
            tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO,
            monto=pago["monto"],
            metodo_pago=pago["metodo_pago"],
            concepto=f"Cobro venta {venta.numero_comprobante}",
            venta=venta,
        )


# ---------------------------------------------------------------- venta presencial

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
    RN-07: subtotales y total los calcula el sistema (con la promoción vigente).
    RN-08: los pagos (uno o varios métodos) tienen que sumar exactamente el total.
    RN-09: la venta presencial exige una caja presencial abierta.
    """
    # ---- 1. Validaciones previas: si algo está mal, no se escribe nada ----
    if caja.tipo_caja != Caja.TipoCaja.PRESENCIAL:
        raise ValidationError({"caja": f"«{caja}» no es una caja presencial."})
    if sesion_abierta(caja) is None:
        raise ValidationError({"caja": f"La caja «{caja}» está cerrada. Ábrala para vender."})

    cantidades = _agrupar(items)
    _verificar_stock(cantidades, SALON)
    lineas = _armar_lineas(cantidades)
    total = sum((linea["subtotal"] for linea in lineas), CERO)
    _validar_pagos(pagos, total)

    # ---- 2. Venta, detalles y stock (sale del salón) ----
    venta = _crear_venta(
        tipo=Venta.TipoVenta.PRESENCIAL,
        cliente=cliente or Cliente.consumidor_final(),
        usuario=usuario,
        total=total,
        observaciones=observaciones,
    )
    _registrar_detalles(venta=venta, lineas=lineas, ubicacion=SALON, usuario=usuario)

    # ---- 3. Cobro en la caja presencial ----
    _registrar_cobros(venta=venta, caja=caja, pagos=pagos)

    return venta


# ---------------------------------------------------------------- venta online

@transaction.atomic
def registrar_venta_online(*, usuario, cliente, items, pagos, entrega,
                           direccion_entrega=None, costo_envio=None,
                           observaciones=None, precios=None, pedido=None):
    """
    Registra una venta online (pedido por WhatsApp, Instagram o la web), en una sola transacción.

    - Exige un cliente identificado: no se admite «Consumidor Final».
    - Descuenta stock del Depósito.
    - Aplica las promociones vigentes, igual que la venta presencial.
    - entrega = RETIRO (retira en el local) o ENVIO (crea el envío en estado Pendiente).
    - El costo del envío se suma al total y no lleva promoción.
    - Se cobra en la caja online; si no tiene sesión abierta, el sistema la abre.
    - No admite efectivo: la caja online no maneja billetes.
    """
    # ---- 1. Validaciones previas ----
    if cliente is None or cliente.es_consumidor_final:
        raise ValidationError({
            "cliente": "La venta online necesita un cliente identificado (no Consumidor Final)."
        })

    if entrega == Entrega.ENVIO:
        if costo_envio is None:
            raise ValidationError({"costo_envio": "Indique el costo del envío (0 si es gratis)."})
    elif entrega == Entrega.RETIRO:
        if costo_envio or direccion_entrega:
            raise ValidationError({
                "entrega": "Una venta con retiro en el local no lleva dirección ni costo de envío."
            })
        costo_envio = CERO
    else:
        raise ValidationError({"entrega": "Indique RETIRO o ENVIO."})

    if any(pago["metodo_pago"].es_efectivo for pago in pagos):
        raise ValidationError({
            "pagos": "La venta online no se cobra en efectivo: la caja online no maneja billetes."
        })

    cantidades = _agrupar(items)
    _verificar_stock(cantidades, DEPOSITO)
    lineas = _lineas_con_precios(cantidades, precios) if precios is not None else _armar_lineas(cantidades)
    total = sum((linea["subtotal"] for linea in lineas), CERO) + costo_envio
    _validar_pagos(pagos, total)

    caja = caja_online()

    # ---- 2. Venta, detalles y stock (sale del depósito) ----
    venta = _crear_venta(
        tipo=Venta.TipoVenta.ONLINE,
        cliente=cliente,
        usuario=usuario,
        total=total,
        observaciones=observaciones,
        pedido=pedido,
    )
    _registrar_detalles(venta=venta, lineas=lineas, ubicacion=DEPOSITO, usuario=usuario)

    # ---- 3. Envío: si falla (por ejemplo, sin dirección), se deshace toda la venta ----
    if entrega == Entrega.ENVIO:
        crear_envio(venta=venta, direccion_entrega=direccion_entrega, costo=costo_envio)

    # ---- 4. Cobro en la caja online (se abre sola si hace falta) ----
    sesion_online(caja=caja, usuario=usuario)
    _registrar_cobros(venta=venta, caja=caja, pagos=pagos)

    return venta


# ---------------------------------------------------------------- anulación

@transaction.atomic
def anular_venta(*, venta, usuario, motivo):
    """
    Anula una venta: la venta no se borra, queda en estado ANULADA (RIR, política general punto 5).
    RN-13: se devuelve el stock con un movimiento de entrada y se registra el egreso en caja.
    El stock vuelve a la ubicación de la que salió (salón o depósito).
    El dinero se devuelve por el mismo método con que se cobró, desde la misma caja:
    la presencial tiene que estar abierta; la online se abre sola si hace falta.
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
        if caja.tipo_caja == Caja.TipoCaja.ONLINE:
            sesion_online(caja=caja, usuario=usuario)
        elif sesion_abierta(caja) is None:
            raise ValidationError({"caja": f"La caja «{caja}» está cerrada. Ábrala para registrar la devolución."})

    # Envíos: si alguno ya salió, se rechaza; si no, los activos pasan a Cancelado
    cancelar_envios_de_venta(venta=venta)
    
    texto = f"Anulada: {motivo}"
    if venta.observaciones:
        texto = f"{venta.observaciones} | {texto}"
    if len(texto) > 500:
        raise ValidationError({"motivo": "El motivo es demasiado largo."})

    # Stock: vuelve a donde salió, vinculado a la venta
    ubicacion = UBICACION_POR_TIPO[venta.tipo]
    for detalle in venta.detalleventa_set.select_related("producto"):
        registrar_entrada(
            producto=detalle.producto,
            ubicacion=ubicacion,
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