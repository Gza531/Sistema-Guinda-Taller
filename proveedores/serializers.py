from rest_framework import serializers

from .models import Proveedor, ProveedorXProducto


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = [
            "id_proveedor",
            "razon_social",
            "cuit",
            "telefono",
            "email",
            "direccion",
            "observaciones",
            "estado",
        ]


class ProveedorXProductoSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(
        source="proveedor.razon_social",
        read_only=True
    )

    producto_nombre = serializers.CharField(
        source="producto.nombre",
        read_only=True
    )

    class Meta:
        model = ProveedorXProducto
        fields = [
            "id_proveedor_producto",
            "proveedor",
            "proveedor_nombre",
            "producto",
            "producto_nombre",
            "precio_compra_referencia",
            "codigo_producto_proveedor",
            "observaciones",
        ]
