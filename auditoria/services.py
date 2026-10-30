"""
Auditoría (Proceso 14 · Gestionar seguridad): quién hizo qué y cuándo.

- registrar(): crea un registro. Lo usan las señales (alta, modificación, baja)
  y el login/logout.
- datos_de(): pasa una fila a un diccionario para guardar en datos_previos / datos_nuevos.

Si no hay un usuario responsable (comando de consola, migración, alguien sin
sesión), no se registra: el DER exige que cada registro tenga su usuario.
"""
import json

from django.core.serializers.json import DjangoJSONEncoder

from .models import Auditoria

# Nunca se guardan en la auditoría (el hash de la contraseña no se expone)
CAMPOS_OCULTOS = {"password", "last_login"}


class _Codificador(DjangoJSONEncoder):
    """Fechas y decimales como texto; lo que no sepa convertir (ej. una imagen), con str()."""

    def default(self, valor):
        try:
            return super().default(valor)
        except TypeError:
            return str(valor)


def datos_de(instancia):
    """{campo: valor} con los campos de la tabla (las FK quedan como id)."""
    return {
        campo.name: campo.value_from_object(instancia)
        for campo in instancia._meta.concrete_fields
        if campo.name not in CAMPOS_OCULTOS
    }


def a_texto(datos):
    """El diccionario como texto JSON (así se guarda en datos_previos / datos_nuevos)."""
    if datos is None:
        return None
    return json.dumps(datos, cls=_Codificador, ensure_ascii=False)


def registrar(*, usuario, accion, tabla, id_registro=None, previos=None, nuevos=None):
    return Auditoria.objects.create(
        usuario=usuario,
        accion=accion,
        tabla_afectada=tabla,
        id_registro_afectado=id_registro,
        datos_previos=a_texto(previos),
        datos_nuevos=a_texto(nuevos),
    )
