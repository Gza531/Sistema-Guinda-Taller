from django.contrib import admin

from .models import Marca, Categoria, Producto, ImagenProducto


class ImagenProductoInline(admin.TabularInline):
    """
    Solo para ver las fotos. Se suben, ordenan y borran por la API,
    que es donde están las reglas (máximo 4, 2 MB, JPG/PNG/WEBP, principal).
    """
    model = ImagenProducto
    extra = 0
    can_delete = False
    fields = ["imagen", "orden", "es_principal"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    inlines = [ImagenProductoInline]


admin.site.register(Marca)
admin.site.register(Categoria)