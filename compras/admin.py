from django.contrib import admin
from .models import Proveedor, Compra, DetalleCompra, ProveedorXProducto


admin.site.register(Proveedor)
admin.site.register(Compra)
admin.site.register(DetalleCompra)
admin.site.register(ProveedorXProducto)
# Register your models here.
