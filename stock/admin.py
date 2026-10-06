from django.contrib import admin
from .models import Stock, MovimientoStock


# Register your models here.

admin.site.register (Stock),
admin.site.register (MovimientoStock)