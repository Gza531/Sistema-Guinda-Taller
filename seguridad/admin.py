from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Empleado, Auditoria

# Register your models here.




@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    pass

admin.site.register(Empleado)
admin.site.register(Auditoria)