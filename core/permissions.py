from rest_framework.permissions import BasePermission, SAFE_METHODS


class PermisoGuinda(BasePermission):
    """Por ahora: lectura libre, escritura con sesión. Después se agregan los roles acá."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


def es_personal(usuario):
    """True si el usuario es un empleado del local o el superusuario."""
    return bool(
        usuario
        and usuario.is_authenticated
        and (usuario.is_superuser or hasattr(usuario, "empleado"))
    )


class EsPersonal(BasePermission):
    """Deja pasar solo a empleados del local y al superusuario."""
    message = "Esta sección es solo para el personal del local."

    def has_permission(self, request, view):
        return es_personal(request.user)


class LecturaPublicaEscrituraPersonal(BasePermission):
    """Cualquiera puede consultar; solo el personal puede crear, editar o dar de baja."""
    message = "Solo el personal del local puede modificar el catálogo."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return es_personal(request.user)