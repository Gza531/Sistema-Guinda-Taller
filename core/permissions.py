# api/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS

class PermisoGuinda(BasePermission):
    """Por ahora: lectura libre, escritura con sesión. Después se agregan los roles acá."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)