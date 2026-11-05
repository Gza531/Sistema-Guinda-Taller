import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from django.db.models import Exists, Max, OuterRef

from catalogo.models import Producto
from stock.models import Stock
from .models import Cliente, Favorito


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

# ---------- Mi perfil (el cliente edita sus propios datos) ----------

DOCUMENTO_FIJO = (
    "Ya tenés compras registradas con este documento, así que no se puede cambiar "
    "desde la tienda. Si hay un error, consultá en el local."
)


def documento_editable(cliente):
    """
    El cliente puede cargar o corregir su documento desde la tienda hasta su primera compra.
    Las ventas no copian el documento: apuntan al cliente. Si lo cambiara después de comprar,
    los comprobantes ya emitidos pasarían a mostrar el documento nuevo.
    Cuenta cualquier venta, también las anuladas (el comprobante ya se emitió).
    """
    return not cliente.nro_documento or not cliente.venta_set.exists()


def _validar_documento(*, cliente, datos):
    """
    Reglas del documento al editar el perfil.
    Si llega el mismo que ya tiene, no hay nada que validar (el formulario lo reenvía tal cual).
    """
    if "tipo_documento" not in datos and "nro_documento" not in datos:
        return

    tipo = datos.get("tipo_documento", cliente.tipo_documento)
    nro = datos.get("nro_documento", cliente.nro_documento)

    if (tipo, nro) == (cliente.tipo_documento, cliente.nro_documento):
        return

    if not documento_editable(cliente):
        raise ValidationError({"nro_documento": DOCUMENTO_FIJO})

    if bool(tipo) != bool(nro):
        raise ValidationError({
            "nro_documento": "El tipo y el número de documento van juntos: completá los dos o ninguno."
        })

    if nro and Cliente.objects.filter(nro_documento=nro).exclude(pk=cliente.pk).exists():
        raise ValidationError({
            "nro_documento": "Ya hay un cliente registrado con ese documento. Consultá en el local."
        })


@transaction.atomic
def actualizar_mi_perfil(*, cliente, datos):
    """
    Guarda los cambios del propio cliente.
    El email vive en dos lugares (Usuario y Cliente) y tiene que quedar igual en ambos:
    el del Usuario es el que usa la recuperación de contraseña.
    """
    # Sin select_related: PostgreSQL no deja bloquear (FOR UPDATE) un JOIN con una FK que admite NULL.
    cliente = Cliente.objects.select_for_update().get(pk=cliente.pk)
    usuario = cliente.usuario

    email = datos.get("email")
    if email is not None:
        if Usuario.objects.filter(email__iexact=email).exclude(pk=usuario.pk).exists():
            raise ValidationError({"email": "Ya existe una cuenta con ese email."})

    _validar_documento(cliente=cliente, datos=datos)

    for campo, valor in datos.items():
        setattr(cliente, campo, valor)
    cliente.save()

    if email is not None and usuario.email != email:
        usuario.email = email
        usuario.save(update_fields=["email"])

    return cliente


@transaction.atomic
def cambiar_mi_password(*, usuario, actual, nueva):
    """El cliente cambia su contraseña: tiene que saber la actual."""
    if not usuario.check_password(actual):
        raise ValidationError({"password_actual": "La contraseña actual no es correcta."})

    if usuario.check_password(nueva):
        raise ValidationError({
            "password_nueva": "La contraseña nueva tiene que ser distinta de la actual."
        })

    try:
        validate_password(nueva, user=usuario)
    except DjangoValidationError as error:
        raise ValidationError({"password_nueva": list(error.messages)})

    usuario.set_password(nueva)
    usuario.save(update_fields=["password"])

# ---------- Mis favoritos ----------

def productos_favoritos(*, cliente):
    """
    Devuelve los favoritos activos del cliente, el último agregado primero.
    Incluye marca, categoría, imágenes y disponibilidad.
    """
    return (
        Producto.objects
        .filter(favoritos__cliente=cliente, estado=True)
        .annotate(fecha_favorito=Max("favoritos__fecha_agregado"))
        .annotate(
            disponible=Exists(
                Stock.objects.filter(
                    producto=OuterRef("pk"),
                    cantidad_actual__gt=0
                )
            )
        )
        .select_related("marca", "categoria")
        .prefetch_related("imagenes")
        .order_by("-fecha_favorito", "-id_producto")
    )


def agregar_favorito(*, cliente, producto):
    """
    Agrega el producto sin duplicarlo.
    Devuelve True si es nuevo y False si ya existía.
    """
    _, creado = Favorito.objects.get_or_create(
        cliente=cliente,
        producto=producto
    )
    return creado


def quitar_favorito(*, cliente, id_producto):
    """Elimina el favorito del cliente, si existe."""
    Favorito.objects.filter(
        cliente=cliente,
        producto_id=id_producto
    ).delete()
