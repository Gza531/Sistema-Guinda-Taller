import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Cliente


Usuario = get_user_model()


def _normalizar(texto):
    """'Díaz ' -> 'diaz': sin tildes, sin espacios de más y en minúsculas."""
    sin_tildes = (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode()
    )
    return " ".join(sin_tildes.lower().split())


def _cliente_a_vincular(*, tipo_documento, nro_documento, apellido, email):
    """
    Busca un cliente cargado en el salón con ese documento.
    Devuelve el cliente si se puede vincular, None si no existe,
    o corta con un error si existe pero no corresponde vincularlo.
    """
    cliente = (
        Cliente.objects.select_for_update()
        .filter(nro_documento=nro_documento)
        .first()
    )

    if cliente is None:
        return None

    if cliente.usuario_id is not None:
        raise ValidationError({
            "nro_documento": (
                "Ya existe una cuenta con ese documento. "
                "Si no recordás tu usuario, consultá en el local."
            )
        })

    if not cliente.estado:
        raise ValidationError({
            "nro_documento": (
                "Ese documento pertenece a un cliente dado de baja. "
                "Consultá en el local."
            )
        })

    if (
        cliente.tipo_documento != tipo_documento
        or _normalizar(cliente.apellido) != _normalizar(apellido)
        or (
            cliente.email
            and cliente.email.strip().casefold() != (email or "").strip().casefold()
        )
    ):
        raise ValidationError({
            "nro_documento": (
                "Los datos no coinciden con el cliente registrado "
                "con ese documento. Consultá en el local."
            )
        })

    return cliente


@transaction.atomic
def registrar_cliente(
    *,
    username,
    password,
    nombre,
    apellido,
    email=None,
    telefono=None,
    direccion=None,
    tipo_documento=None,
    nro_documento=None,
):
    cliente = None

    if nro_documento:
        cliente = _cliente_a_vincular(
            tipo_documento=tipo_documento,
            nro_documento=nro_documento,
            apellido=apellido,
            email=email,
        )

    usuario = Usuario.objects.create_user(
        username=username,
        password=password,
        email=email or "",
    )

    grupo_cliente, _ = Group.objects.get_or_create(name="Cliente")
    usuario.groups.add(grupo_cliente)

    if cliente is not None:
        cliente.usuario = usuario

        for campo, valor in (
            ("email", email),
            ("telefono", telefono),
            ("direccion", direccion),
        ):
            if valor and not getattr(cliente, campo):
                setattr(cliente, campo, valor)

        cliente.save()
        return cliente, True

    cliente = Cliente.objects.create(
        usuario=usuario,
        nombre=nombre,
        apellido=apellido,
        email=email or None,
        telefono=telefono or None,
        direccion=direccion or None,
        tipo_documento=tipo_documento,
        nro_documento=nro_documento,
    )

    return cliente, False