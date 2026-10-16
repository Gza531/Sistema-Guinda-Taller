from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Empleado, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    pass


admin.site.register(Empleado)
