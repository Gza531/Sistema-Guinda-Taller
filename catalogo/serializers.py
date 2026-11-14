from rest_framework import serializers

from promociones.services import descuento_vigente
from stock.models import Stock

from .models import Categoria, ImagenProducto, Marca, Producto


class NombreUnicoMixin:
    """
    El nombre no puede repetirse aunque cambien mayúsculas o espacios:
    «Dior», «dior» y « DIOR » son la misma marca.
    """
    etiqueta = "un registro"  # cada serializer dice "una marca", "una categoría"...

    def validate_nombre(self, valor):
        nombre = " ".join(valor.split())  # saca espacios de más, también en el medio
        modelo = self.Meta.model
        repetido = modelo.objects.filter(nombre__iexact=nombre)
        if self.instance is not None:
            repetido = repetido.exclude(pk=self.instance.pk)
        existente = repetido.first()
        if existente:
            raise serializers.ValidationError(
                f"Ya existe {self.etiqueta} llamada «{existente.nombre}»."
            )
        return nombre


class MarcaSerializer(NombreUnicoMixin, serializers.ModelSerializer):
    etiqueta = "una marca"

    class Meta:
        model = Marca
        fields = "__all__"
        # La unicidad la controla validate_nombre (sin distinguir mayúsculas)
        extra_kwargs = {"nombre": {"validators": []}}


class CategoriaSerializer(NombreUnicoMixin, serializers.ModelSerializer):
    etiqueta = "una categoría"

    class Meta:
        model = Categoria
        fields = "__all__"
        extra_kwargs = {"nombre": {"validators": []}}

class ImagenProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenProducto
        fields = ["id_imagen_producto", "imagen", "orden", "es_principal"]
        read_only_fields = fields


class ProductoSerializer(serializers.ModelSerializer):
    marca_nombre = serializers.CharField(
        source="marca.nombre",
        read_only=True
    )

    categoria_nombre = serializers.CharField(
        source="categoria.nombre",
        read_only=True
    )

    disponible = serializers.SerializerMethodField()
    precio_promocional = serializers.SerializerMethodField()
    
    # "imagen" es la URL de la foto principal (la usan las tarjetas del catálogo)
    imagen = serializers.SerializerMethodField()
    imagenes = ImagenProductoSerializer(many=True, read_only=True)

    def get_disponible(self, obj):
        if hasattr(obj, "disponible"):
            return obj.disponible

        # Igual que en ProductoViewSet: disponible para la tienda = hay en el Depósito
        return Stock.objects.filter(
            producto=obj,
            ubicacion=Stock.Ubicaciones.DEPOSITO,
            cantidad_actual__gt=0,
        ).exists()

    def get_imagen(self, obj):
        imagenes = list(obj.imagenes.all())
        if not imagenes:
            return None

        # Si por algún motivo ninguna está marcada, se usa la primera
        principal = next((i for i in imagenes if i.es_principal), imagenes[0])

        request = self.context.get("request")
        url = principal.imagen.url
        return request.build_absolute_uri(url) if request else url

    def get_precio_promocional(self, obj):
        promocion, monto = descuento_vigente(obj)

        if promocion is None:
            return None

        return str(obj.precio_venta - monto)

    class Meta:
        model = Producto
        fields = "__all__"



class SubirImagenesSerializer(serializers.Serializer):
    imagenes = serializers.ListField(
        child=serializers.ImageField(),
        allow_empty=False
    )


class OrdenImagenesSerializer(serializers.Serializer):
    orden = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
