"""
Registro automático de altas, modificaciones y bajas.

Se auditan los maestros y las operaciones. No se auditan los renglones
(detalles de venta, compra, pedido) ni los movimientos de stock y de caja:
esas tablas ya son, en sí mismas, un historial con usuario y fecha.

Ojo: las señales no se disparan con QuerySet.update() ni bulk_create().
Por eso en los modelos auditados se guarda siempre con .save().
"""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save

from .contexto import usuario_actual
from .models import Auditoria
from .services import a_texto, datos_de, registrar

MODELOS_AUDITADOS = [
    "catalogo.Marca",
    "catalogo.Categoria",
    "catalogo.Producto",
    "promociones.Promocion",
    "clientes.Cliente",
    "proveedores.Proveedor",
    "seguridad.Usuario",
    "seguridad.Empleado",
    "cajas.Caja",
    "cajas.MetodoPago",
    "cajas.AperturaCierreCaja",
    "ventas.Venta",
    "compras.Compra",
    "pedidos.Pedido",
    "envios.Envio",
]


def _guardar_previo(sender, instance, raw=False, **kwargs):
    """Antes de guardar, lee cómo estaba la fila en la base (para datos_previos)."""
    if raw or instance.pk is None or usuario_actual() is None:
        return
    previo = sender._base_manager.filter(pk=instance.pk).first()
    instance._auditoria_previo = datos_de(previo) if previo else None
    instance._auditoria_password_previa = getattr(previo, "password", None)


def _auditar_guardado(sender, instance, created, raw=False, **kwargs):
    usuario = usuario_actual()
    if raw or usuario is None:
        return

    tabla = sender._meta.db_table
    nuevos = datos_de(instance)

    if created:
        registrar(usuario=usuario, accion=Auditoria.Accion.INSERT, tabla=tabla,
                  id_registro=instance.pk, nuevos=nuevos)
        return

    previos = getattr(instance, "_auditoria_previo", None) or {}
    # En una modificación se guardan solo los campos que cambiaron
    cambiados = [campo for campo, valor in nuevos.items() if previos.get(campo) != valor]
    antes = {campo: previos.get(campo) for campo in cambiados}
    despues = {campo: nuevos[campo] for campo in cambiados}

    # La contraseña no se muestra, pero sí que se cambió
    password_previa = getattr(instance, "_auditoria_password_previa", None)
    if password_previa is not None and password_previa != getattr(instance, "password", None):
        antes["password"] = "********"
        despues["password"] = "(modificada)"

    if despues:
        registrar(usuario=usuario, accion=Auditoria.Accion.UPDATE, tabla=tabla,
                  id_registro=instance.pk, previos=antes, nuevos=despues)


def _auditar_borrado(sender, instance, **kwargs):
    usuario = usuario_actual()
    if usuario is None:
        return
    registrar(usuario=usuario, accion=Auditoria.Accion.DELETE, tabla=sender._meta.db_table,
              id_registro=instance.pk, previos=datos_de(instance))


def _nombres_de_roles(usuario):
    return sorted(usuario.groups.values_list("name", flat=True))


def _auditar_roles(sender, instance, action, reverse, **kwargs):
    """
    Los roles (grupos) son una relación muchos-a-muchos: no pasan por post_save.
    groups.set() puede disparar un "quitar" y después un "agregar": se junta todo
    en un solo registro (roles antes → roles después).
    """
    Usuario = get_user_model()
    if reverse or not isinstance(instance, Usuario):
        return

    if action.startswith("pre_"):
        if not hasattr(instance, "_auditoria_roles_previos"):
            instance._auditoria_roles_previos = _nombres_de_roles(instance)
        return
    if not action.startswith("post_"):
        return

    usuario = usuario_actual()
    if usuario is None:
        return

    antes = {"roles": instance._auditoria_roles_previos}
    despues = {"roles": _nombres_de_roles(instance)}
    registro = getattr(instance, "_auditoria_registro_roles", None)

    if registro is not None:
        registro.datos_nuevos = a_texto(despues)
        registro.save(update_fields=["datos_nuevos"])
    elif antes != despues:
        instance._auditoria_registro_roles = registrar(
            usuario=usuario, accion=Auditoria.Accion.UPDATE,
            tabla=Usuario._meta.db_table, id_registro=instance.pk,
            previos=antes, nuevos=despues,
        )


def conectar():
    for etiqueta in MODELOS_AUDITADOS:
        modelo = apps.get_model(etiqueta)
        uid = f"auditoria_{etiqueta}"
        pre_save.connect(_guardar_previo, sender=modelo, dispatch_uid=f"{uid}_pre")
        post_save.connect(_auditar_guardado, sender=modelo, dispatch_uid=f"{uid}_post")
        post_delete.connect(_auditar_borrado, sender=modelo, dispatch_uid=f"{uid}_del")

    m2m_changed.connect(_auditar_roles, sender=get_user_model().groups.through,
                        dispatch_uid="auditoria_roles")
