"""
Reglas de negocio de Empleados (Seguridad).

- Un empleado es un Usuario (para iniciar sesión) + un Empleado (datos personales).
- Los roles son grupos de Django; un empleado puede tener varios.
- Baja lógica: estado = False en el empleado y is_active = False en el usuario
  (así ya no puede iniciar sesión).
- Solo la Dueña (o el superusuario) gestiona a otra Dueña y asigna ese rol.
- Nadie puede darse de baja ni cambiar sus propios roles (evita quedarse afuera).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.permissions import DUENA, TODO_EL_PERSONAL, roles_de

from .models import Empleado


Usuario = get_user_model()


# ---------- Ayudas ----------


# Sirve para identificar si el usuario es superusuario o pertenece al rol Dueña

def _es_duena(usuario):
    return usuario.is_superuser or DUENA in roles_de(usuario)


# Devolver un conjunto de roles

def _roles_del_empleado(empleado):
    if not empleado.usuario:
        return set()
    return set(empleado.usuario.groups.values_list("name", flat=True))

# Bloquear la petición si se quiere modificar a la dueña pero no sos dueña ni superusuario

def _verificar_puede_gestionar(*, actor, empleado):
    """Una Encargada no puede tocar a un empleado que es Dueña."""
    if DUENA in _roles_del_empleado(empleado) and not _es_duena(actor):
        raise PermissionDenied("Solo la Dueña puede modificar a otra Dueña.")

# Se bloquea la acción si es la misma cuenta

def _verificar_no_es_uno_mismo(*, actor, empleado, accion):
    if empleado.usuario_id and empleado.usuario_id == actor.pk:
        raise PermissionDenied(f"No podés {accion} tu propio usuario.")

# Revisa si los roles solicitados son válidos y si el actor puede asignarlos
# Si está tdoo bien, devuelve los grupos de Django correspondientes

def _grupos(*, actor, roles):
    """Valida la lista de roles y devuelve los grupos."""
    roles = set(roles)
    if not roles:
        raise ValidationError({"roles": "Asigná al menos un rol."})

    desconocidos = roles - TODO_EL_PERSONAL
    if desconocidos:
        raise ValidationError({"roles": f"Roles inválidos: {', '.join(sorted(desconocidos))}."})

    if DUENA in roles and not _es_duena(actor):
        raise PermissionDenied("Solo la Dueña puede asignar el rol Dueña.")

    return list(Group.objects.filter(name__in=roles))

#Revisar si una contraseña cumple nuestras reglas, se utiliza el validador de Django

def _validar_password(password, usuario=None):
    try:
        validate_password(password, user=usuario)
    except DjangoValidationError as e:
        raise ValidationError({"password": list(e.messages)})


# ---------- Casos de uso ----------

# Validamos el nombre de usuario, contraseña y roles
# Creamos la cuenta con sus roles y se vincula a la ficha del empleado
# Si el alta falla, se deshacen los cambios gracias al Transaction.atomic

@transaction.atomic
def crear_empleado(*, actor, username, password, roles, nombre, apellido,
                   dni=None, telefono=None, email=None):
    grupos = _grupos(actor=actor, roles=roles)

    if Usuario.objects.filter(username__iexact=username).exists():
        raise ValidationError({"username": "Ya existe un usuario con ese nombre."})

    usuario = Usuario(username=username, email=email or "",
                      first_name=nombre, last_name=apellido)
    _validar_password(password, usuario)
    usuario.set_password(password)
    usuario.save()
    usuario.groups.set(grupos)

    return Empleado.objects.create(
        usuario=usuario, nombre=nombre, apellido=apellido,
        dni=dni, telefono=telefono, email=email,
    )

# Actualiza la ficha del empleado y sincroniza los datos de su cuenta
# Si se solicita y está permitido, cambia sus roles o reactiva su acceso
# Bloquea la ficha durante la edición y deshace cambios si algo falla


@transaction.atomic
def actualizar_empleado(*, actor, empleado, datos):
    """
    datos puede traer: nombre, apellido, dni, telefono, email, roles, estado.
    estado = True reactiva al empleado (y le devuelve el acceso).
    """
    empleado = Empleado.objects.select_for_update().get(pk=empleado.pk)
    _verificar_puede_gestionar(actor=actor, empleado=empleado)

    roles = datos.pop("roles", None)
    estado = datos.pop("estado", None)

    for campo, valor in datos.items():
        setattr(empleado, campo, valor)

    if estado is False:
        raise ValidationError({"estado": "Para dar de baja use DELETE."})
    if estado is True:
        empleado.estado = True

    empleado.save()

    usuario = empleado.usuario
    if usuario:
        usuario.first_name = empleado.nombre
        usuario.last_name = empleado.apellido
        usuario.email = empleado.email or ""
        if estado is True:
            usuario.is_active = True
        usuario.save()

        if roles is not None:
            _verificar_no_es_uno_mismo(actor=actor, empleado=empleado, accion="cambiar los roles de")
            usuario.groups.set(_grupos(actor=actor, roles=roles))

    return empleado


# Dá de baja al empleado y deshabilita su cuenta si es que tiene una asociada

@transaction.atomic
def dar_de_baja(*, actor, empleado):
    empleado = Empleado.objects.select_for_update().get(pk=empleado.pk)
    _verificar_puede_gestionar(actor=actor, empleado=empleado)
    _verificar_no_es_uno_mismo(actor=actor, empleado=empleado, accion="dar de baja")

    empleado.estado = False
    empleado.save(update_fields=["estado"])

    if empleado.usuario:
        empleado.usuario.is_active = False
        empleado.usuario.save(update_fields=["is_active"])

    return empleado


# Se verifica que el actor pueda gestionar al empleado y si tiene una cuenta
# Valida la contraseña nueva y guarda el hash en la cuenta del empleado

@transaction.atomic
def cambiar_password(*, actor, empleado, password):
    _verificar_puede_gestionar(actor=actor, empleado=empleado)

    usuario = empleado.usuario
    if not usuario:
        raise ValidationError({"password": "Este empleado no tiene usuario para iniciar sesión."})

    _validar_password(password, usuario)
    usuario.set_password(password)
    usuario.save(update_fields=["password"])
    return empleado