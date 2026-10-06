from django.contrib import admin
from .models import Caja, MovimientoCaja, AperturaCierreCaja ,MetodoPago
# Register your models here.

admin.site.register (Caja)
admin.site.register (MovimientoCaja)
admin.site.register (AperturaCierreCaja)
admin.site.register (MetodoPago)