from rest_framework import serializers
from catalogo.models import Producto


class ProductoSerializer(serializers.ModelSerializer):
    marca_nombre = serializers.CharField(
        source="marca.nombre",
        read_only=True
    )

    categoria_nombre = serializers.CharField(
        source="categoria.nombre",
        read_only=True
    )

    class Meta:
        model = Producto
        fields = "__all__"