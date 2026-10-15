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