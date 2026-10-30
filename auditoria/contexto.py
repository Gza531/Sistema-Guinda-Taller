"""
¿Quién está haciendo la operación? (para la auditoría)

Las señales de Django (post_save, post_delete) no reciben el request, así que no
saben qué usuario guardó. Este middleware guarda el request actual en una
ContextVar (una "variable por request", segura con varios requests a la vez)
y usuario_actual() lo lee desde cualquier parte del código.

Con JWT, DRF autentica dentro de la vista y copia el usuario al request de
Django (request.user); por eso, cuando se dispara la señal, el usuario ya está.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from core.permissions import es_personal

_request_actual = ContextVar("auditoria_request_actual", default=None)
_usuario_forzado = ContextVar("auditoria_usuario_forzado", default=None)


class AuditoriaMiddleware:
    """Guarda el request mientras dura, para que la auditoría sepa quién opera."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _request_actual.set(request)
        try:
            return self.get_response(request)
        finally:
            _request_actual.reset(token)

def usuario_actual():
    """
    El empleado que hace la operación, o None si no hay que auditar:
    cliente de la tienda, alguien sin sesión, comando de consola o migración.
    """
    usuario = _usuario_forzado.get()
    if usuario is None:
        request = _request_actual.get()
        usuario = getattr(request, "user", None)
    return usuario if es_personal(usuario) else None


@contextmanager
def como_usuario(usuario):
    """
    Para operaciones sin sesión que igual tienen un responsable.
    Ej.: el webhook de Mercado Pago registra la venta a nombre del cliente.
    """
    token = _usuario_forzado.set(usuario)
    try:
        yield
    finally:
        _usuario_forzado.reset(token)
