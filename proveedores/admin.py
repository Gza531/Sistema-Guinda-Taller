from django.contrib import admin

from .models import Proveedor, ProveedorXProducto

admin.site.register(Proveedor)
admin.site.register(ProveedorXProducto)
