import os
import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as ErrorDeDjango
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
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


# ---------------- Recuperar contraseña (solo clientes de la tienda) ----------------
# El personal no recupera por mail: a un empleado le cambia la contraseña la Dueña
# desde Empleados (así alguien dado de baja no puede volver a entrar por esta vía).
#
# El token es el de Django (default_token_generator): no se guarda en ninguna tabla,
# se calcula con los datos del usuario. Por eso deja de servir apenas se cambia la
# contraseña (un solo uso) y vence solo (PASSWORD_RESET_TIMEOUT en settings).

LINK_INVALIDO = "El link no es válido o ya venció. Pedí uno nuevo."


def _clientes_que_pueden_recuperar():
    return Usuario.objects.filter(
        is_active=True,
        cliente__isnull=False,
        cliente__estado=True,
        empleado__isnull=True,
        is_superuser=False,
    )


def _link_de_recuperacion(usuario):
    front = os.environ.get("FRONT_URL", "").strip().rstrip("/") or "http://localhost:5173"
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return f"{front}/restablecer/{uid}/{token}"


def enviar_recuperacion(email):
    """
    Si el email es de un cliente, le manda el link para elegir una contraseña nueva.
    No avisa si el email no existe: la vista responde siempre lo mismo.
    """
    email = (email or "").strip()

    for usuario in _clientes_que_pueden_recuperar().filter(email__iexact=email):
        send_mail(
            subject="Guinda Perfumería · Recuperá tu contraseña",
            message=(
                f"Hola {usuario.cliente.nombre}:\n\n"
                "Recibimos un pedido para cambiar la contraseña de tu cuenta "
                f"«{usuario.username}» en Guinda Perfumería.\n\n"
                "Para elegir una nueva, entrá a este link (vence en 1 hora):\n"
                f"{_link_de_recuperacion(usuario)}\n\n"
                "Si no lo pediste, ignorá este mail: tu contraseña no cambia."
            ),
            from_email=None,            # usa DEFAULT_FROM_EMAIL
            recipient_list=[usuario.email],
        )


def restablecer_password(*, uid, token, password):
    """Verifica el link y guarda la contraseña nueva. El link queda usado."""
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        usuario = _clientes_que_pueden_recuperar().get(pk=pk)
    except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
        raise ValidationError({"detail": LINK_INVALIDO})

    if not default_token_generator.check_token(usuario, token):
        raise ValidationError({"detail": LINK_INVALIDO})

    try:
        validate_password(password, usuario)
    except ErrorDeDjango as error:
        raise ValidationError({"password": list(error.messages)})

    usuario.set_password(password)
    usuario.save(update_fields=["password"])
    return usuario

