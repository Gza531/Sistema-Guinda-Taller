"""
Reglas de negocio del módulo Caja (DFD: Gestionar apertura y cierre de caja).
"""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import AperturaCierreCaja, Caja


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