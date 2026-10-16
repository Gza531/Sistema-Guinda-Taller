from rest_framework import serializers
from catalogo.models import Producto, Marca, Categoria
from stock.models import Stock


class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        fields = "__all__"


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = "__all__"


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

    def get_disponible(self, obj):
        if hasattr(obj, "disponible"):
            return obj.disponible

        return Stock.objects.filter(
            producto=obj,
            cantidad_actual__gt=0
        ).exists()

    class Meta:
        model = Producto
        fields = "__all__"