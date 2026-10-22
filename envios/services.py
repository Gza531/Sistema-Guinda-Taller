"""
Reglas de negocio del módulo Envíos.

Un envío permite seguir el paquete de una venta online.
No modifica stock ni caja: esas operaciones corresponden a Ventas.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ventas.models import Venta

from .models import Envio


E = Envio.EstadoEnvio


# RN-47: cambios de estado permitidos.
TRANSICIONES = {
    E.PENDIENTE: {E.PREPARADO},
    E.PREPARADO: {E.DESPACHADO},
    E.DESPACHADO: {E.EN_TRANSITO, E.DEMORADO, E.ENTREGADO},
    E.EN_TRANSITO: {E.DEMORADO, E.ENTREGADO, E.DEVUELTO},
    E.DEMORADO: {E.EN_TRANSITO, E.ENTREGADO, E.DEVUELTO},
}


# Solo se pueden corregir datos antes de despachar.
EDITABLES = {E.PENDIENTE, E.PREPARADO}

# El paquete ya salió del local (o llegó): la venta no se puede anular.
EN_CAMINO = {E.DESPACHADO, E.EN_TRANSITO, E.DEMORADO, E.ENTREGADO}


@transaction.atomic
def crear_envio(
    *,
    venta,
    direccion_entrega=None,
    costo=None,
    empresa_transporte=None,
    codigo_seguimiento=None
):
    venta = Venta.objects.select_for_update().select_related("cliente").get(pk=venta.pk)

    if Envio.objects.filter(venta=venta).exclude(estado=E.DEVUELTO).exists():
        raise ValidationError({
            "venta": f"La venta {venta.numero_comprobante} ya tiene un envío."
        })

    if venta.tipo != Venta.TipoVenta.ONLINE:
        raise ValidationError({
            "venta": "Solo las ventas online generan envíos. Una venta presencial se entrega en el local."
        })

    if venta.estado == Venta.EstadoVenta.ANULADA:
        raise ValidationError({
            "venta": f"La venta {venta.numero_comprobante} está anulada."
        })

    direccion = (direccion_entrega or "").strip()

    if not direccion:
        direccion = (venta.cliente.direccion or "").strip()

    if not direccion:
        raise ValidationError({
            "direccion_entrega": "Indique la dirección de entrega: el cliente no tiene una cargada."
        })

    return Envio.objects.create(
        venta=venta,
        direccion_entrega=direccion,
        costo=costo,
        empresa_transporte=(empresa_transporte or "").strip() or None,
        codigo_seguimiento=(codigo_seguimiento or "").strip() or None
    )


@transaction.atomic
def actualizar_envio(*, envio, **datos):
    envio = Envio.objects.select_for_update().get(pk=envio.pk)

    if envio.estado not in EDITABLES:
        raise ValidationError({
            "estado": (
                f"Un envío {envio.get_estado_display()} "
                "ya no se puede modificar."
            )
        })

    for campo, valor in datos.items():
        if campo in {
            "direccion_entrega",
            "empresa_transporte",
            "codigo_seguimiento"
        }:
            valor = (valor or "").strip() or None

        setattr(envio, campo, valor)

    if not envio.direccion_entrega:
        raise ValidationError({
            "direccion_entrega": "La dirección de entrega es obligatoria."
        })

    envio.save()

    return envio


@transaction.atomic
def cambiar_estado(
    *,
    envio,
    estado,
    empresa_transporte=None,
    codigo_seguimiento=None
):
    envio = Envio.objects.select_for_update().get(pk=envio.pk)

    permitidos = TRANSICIONES.get(envio.estado, set())

    if estado not in permitidos:
        if not permitidos:
            mensaje = (
                f"Un envío {envio.get_estado_display()} "
                "ya no cambia de estado."
            )
        else:
            destinos = ", ".join(
                E(valor).label for valor in sorted(permitidos)
            )
            mensaje = (
                f"Un envío {envio.get_estado_display()} "
                f"solo puede pasar a: {destinos}."
            )

        raise ValidationError({"estado": mensaje})

    campos = ["estado"]

    if estado == E.DESPACHADO:
        empresa = (
            (empresa_transporte or "").strip()
            or (envio.empresa_transporte or "").strip()
        )

        if not empresa:
            raise ValidationError({
                "empresa_transporte": (
                    "Para despachar hay que indicar "
                    "la empresa de transporte."
                )
            })

        envio.empresa_transporte = empresa
        envio.fecha_despacho = timezone.now()

        campos.extend(["empresa_transporte", "fecha_despacho"])

        codigo = (codigo_seguimiento or "").strip()

        if codigo:
            envio.codigo_seguimiento = codigo
            campos.append("codigo_seguimiento")

    envio.estado = estado
    envio.save(update_fields=campos)

    return envio


@transaction.atomic
def eliminar_envio(*, envio):
    envio = Envio.objects.select_for_update().get(pk=envio.pk)

    if envio.estado != E.PENDIENTE:
        raise ValidationError({
            "estado": (
                f"Un envío {envio.get_estado_display()} "
                "no se puede eliminar."
            )
        })

    envio.delete()



@transaction.atomic
def cancelar_envios_de_venta(*, venta):
    """
    Se llama al anular una venta.
    Solo se puede anular si ningún envío salió del local: los Pendientes o Preparados
    pasan a Cancelado y los Devueltos quedan como están (el paquete ya volvió).
    Cancelado es un estado final: no se llega desde /estado/, solo anulando la venta.
    """
    envios = list(Envio.objects.select_for_update().filter(venta=venta))

    for envio in envios:
        if envio.estado == E.ENTREGADO:
            raise ValidationError({
                "envio": (
                    f"El envío {envio.id_envio} ya fue entregado: "
                    "no corresponde anular la venta sino gestionar una devolución."
                )
            })
        if envio.estado in EN_CAMINO:
            raise ValidationError({
                "envio": (
                    f"El envío {envio.id_envio} está {envio.get_estado_display()}: "
                    "la venta se puede anular cuando el paquete vuelva (Devuelto)."
                )
            })

    for envio in envios:
        if envio.estado in EDITABLES:
            envio.estado = E.CANCELADO
            envio.save(update_fields=["estado"])