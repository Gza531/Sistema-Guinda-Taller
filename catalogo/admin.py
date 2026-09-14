from django.contrib import admin

# Register your models here.

from .models import Marca, Categoria, Producto

admin.site.register(Marca)
admin.site.register(Categoria)
admin.site.register(Producto)