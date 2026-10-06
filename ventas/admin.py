from django.contrib import admin
from .models import Cliente, Pedido, DetallePedido, Venta, DetalleVenta, Envio

# Register your models here.


admin.site.register(Cliente)
admin.site.register(Pedido)
admin.site.register(DetallePedido)
admin.site.register(Venta)
admin.site.register(DetalleVenta)
admin.site.register(Envio)