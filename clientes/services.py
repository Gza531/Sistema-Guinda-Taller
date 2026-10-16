from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from .models import Cliente

Usuario = get_user_model()

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
    usuario = Usuario.objects.create_user(
        username=username,
        password=password,
        email=email or "",
    )

    grupo_cliente, _ = Group.objects.get_or_create(name="Cliente")
    usuario.groups.add(grupo_cliente)

    cliente = Cliente.objects.create(
        usuario=usuario,
        nombre=nombre,
        apellido=apellido,
        email=email,
        telefono=telefono,
        direccion=direccion,
        tipo_documento=tipo_documento,
        nro_documento=nro_documento,
    )

    return cliente