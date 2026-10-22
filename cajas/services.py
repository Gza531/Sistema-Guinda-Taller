"""
Reglas de negocio del módulo Caja (DFD: Gestionar apertura y cierre de caja).
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import AperturaCierreCaja, Caja, MetodoPago, MovimientoCaja


def sesion_abierta(caja):
    """Devuelve la sesión abierta de la caja, o None si está cerrada."""
    return AperturaCierreCaja.objects.filter(
        caja=caja, fecha_cierre__isnull=True
    ).first()


@transaction.atomic
def abrir_caja(*, caja, usuario, monto_inicial, observaciones=None):
    """
    Abre una sesión de caja.
    RN-15: una caja solo puede tener una sesión abierta a la vez.
    RN-16: se registran el monto inicial, el responsable y la fecha y hora.
    """
    # Bloquea la fila de la caja hasta que termine la transacción,
    # para que dos personas no la abran al mismo tiempo.
    caja = Caja.objects.select_for_update().get(pk=caja.pk)

    if not caja.estado:
        raise ValidationError({"caja": f"La caja «{caja}» está dada de baja."})

    if sesion_abierta(caja):
        raise ValidationError({"caja": f"La caja «{caja}» ya está abierta."})

    return AperturaCierreCaja.objects.create(
        caja=caja,
        usuario=usuario,
        monto_inicial=monto_inicial,
        observaciones=observaciones,
    )

def caja_online():
    """Devuelve la caja online habilitada (la que registra los cobros de la tienda web)."""
    caja = (
        Caja.objects
        .filter(tipo_caja=Caja.TipoCaja.ONLINE, estado=True)
        .order_by("id_caja")
        .first()
    )
    if caja is None:
        raise ValidationError({"caja": "No hay una caja online habilitada. Créela desde Cajas."})
    return caja


@transaction.atomic
def sesion_online(*, caja, usuario):
    """
    Devuelve la sesión abierta de la caja online. Si no hay, la abre el sistema
    con monto inicial 0: los cobros online llegan a cualquier hora y no hay nadie
    para abrirla (excepción a RN-17 solo para la caja online).
    El corte lo hace la Encargada al cerrarla, conciliando con el reporte de cobros;
    el siguiente cobro abre una sesión nueva.
    """
    # Bloquea la caja: si llegan dos cobros a la vez, el segundo espera
    # y encuentra la sesión que abrió el primero (RN-15: una sola sesión abierta).
    caja = Caja.objects.select_for_update().get(pk=caja.pk)

    if caja.tipo_caja != Caja.TipoCaja.ONLINE:
        raise ValidationError({"caja": f"«{caja}» no es una caja online."})

    sesion = sesion_abierta(caja)
    if sesion is not None:
        return sesion

    return abrir_caja(
        caja=caja,
        usuario=usuario,
        monto_inicial=Decimal("0.00"),
        observaciones="Apertura automática del sistema",
    )


def resumen_sesion(sesion):
    """
    Calcula el arqueo de una sesión de caja (RN-22).
    Solo el efectivo se compara con lo contado; los demás métodos se informan por separado.
    """
    movimientos = MovimientoCaja.objects.filter(apertura_cierre=sesion)
    Tipo = MovimientoCaja.TipoMovimiento
    cero = Decimal("0.00")

    efectivo = movimientos.filter(metodo_pago__nombre=MetodoPago.EFECTIVO)
    ingresos_efectivo = efectivo.filter(tipo_movimiento=Tipo.INGRESO).aggregate(
        total=Sum("monto", default=cero))["total"]
    egresos_efectivo = efectivo.filter(tipo_movimiento=Tipo.EGRESO).aggregate(
        total=Sum("monto", default=cero))["total"]
    esperado = sesion.monto_inicial + ingresos_efectivo - egresos_efectivo

    por_metodo = (
        movimientos.values("metodo_pago__nombre")
        .annotate(
            ingresos=Sum("monto", filter=Q(tipo_movimiento=Tipo.INGRESO), default=cero),
            egresos=Sum("monto", filter=Q(tipo_movimiento=Tipo.EGRESO), default=cero),
        )
        .order_by("metodo_pago__nombre")
    )

    return {
        "monto_inicial": sesion.monto_inicial,
        "ingresos_efectivo": ingresos_efectivo,
        "egresos_efectivo": egresos_efectivo,
        "efectivo_esperado": esperado,
        "efectivo_contado": sesion.monto_final,
        "diferencia": None if sesion.monto_final is None else sesion.monto_final - esperado,
        "por_metodo": [
            {"metodo": f["metodo_pago__nombre"], "ingresos": f["ingresos"], "egresos": f["egresos"]}
            for f in por_metodo
        ],
    }


@transaction.atomic
def cerrar_caja(*, sesion, monto_final, observaciones=None):
    """
    Cierra una sesión de caja con el efectivo contado.
    RN-24: una sesión cerrada no se reabre ni se modifica.
    La observación es opcional, aunque haya diferencia.
    """
    sesion = AperturaCierreCaja.objects.select_for_update().get(pk=sesion.pk)

    if sesion.fecha_cierre is not None:
        raise ValidationError({"sesion": "Esta sesión de caja ya está cerrada."})

    if observaciones:
        texto = f"Cierre: {observaciones}"
        if sesion.observaciones:
            texto = f"{sesion.observaciones} | {texto}"
        if len(texto) > 500:
            raise ValidationError({"observaciones": "Las observaciones son demasiado largas."})
        sesion.observaciones = texto

    sesion.fecha_cierre = timezone.now()
    sesion.monto_final = monto_final
    sesion.save(update_fields=["fecha_cierre", "monto_final", "observaciones"])
    return sesion

@transaction.atomic
def registrar_movimiento_caja(*, caja, tipo_movimiento, monto, metodo_pago,
                              concepto=None, venta=None, compra=None):
    """
    Registra un ingreso o egreso en la sesión abierta de una caja.
    Es la función que comparten los movimientos manuales, la venta y el pago de compras.
    RN-17: solo se registran movimientos con la caja abierta.
    RN-18: solo con métodos de pago habilitados.
    RN-19: un movimiento corresponde a una venta, a una compra o a ninguna, nunca a ambas.
    RN-21: un egreso manual (sin venta ni compra) tiene que indicar el concepto.
    """
    sesion = sesion_abierta(caja)
    if sesion is None:
        raise ValidationError({"caja": f"La caja «{caja}» está cerrada. Ábrala para registrar movimientos."})

    # Bloquea la sesión: así nadie la cierra mientras se registra este movimiento.
    sesion = AperturaCierreCaja.objects.select_for_update().get(pk=sesion.pk)
    if sesion.fecha_cierre is not None:
        raise ValidationError({"caja": f"La caja «{caja}» se cerró recién. Vuelva a abrirla."})

    if not metodo_pago.estado:
        raise ValidationError({"metodo_pago": f"El método de pago «{metodo_pago}» está dado de baja."})

    if monto <= 0:
        raise ValidationError({"monto": "El monto debe ser mayor que cero."})

    if venta is not None and compra is not None:
        raise ValidationError({"detail": "Un movimiento no puede corresponder a una venta y a una compra a la vez."})

    concepto = (concepto or "").strip() or None
    es_manual = venta is None and compra is None
    if es_manual and not concepto:
        raise ValidationError({"concepto": "Indique el motivo del movimiento (por ejemplo: «Pago de luz» o «Aporte para cambio»)."})

    return MovimientoCaja.objects.create(
        apertura_cierre=sesion,
        tipo_movimiento=tipo_movimiento,
        monto=monto,
        metodo_pago=metodo_pago,
        concepto=concepto,
        venta=venta,
        compra=compra,
    )