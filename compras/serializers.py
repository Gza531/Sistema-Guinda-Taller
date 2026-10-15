from rest_framework import serializers

from .models import Proveedor, ProveedorXProducto, Compra, DetalleCompra
from decimal import Decimal
from catalogo.models import Producto


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

class CompraSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(
        source="proveedor.razon_social",
        read_only=True
    )

    usuario_username = serializers.CharField(
        source="usuario.username",
        read_only=True
    )

    class Meta:
        model = Compra
        fields = [
            "id_compra",
            "fecha",
            "numero_factura",
            "total",
            "estado",
            "observaciones",
            "proveedor",
            "proveedor_nombre",
            "usuario",
            "usuario_username",
        ]


class DetalleCompraSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(
        source="producto.nombre",
        read_only=True
    )

    class Meta:
        model = DetalleCompra
        fields = [
            "id_detalle_compra",
            "cantidad",
            "precio_unitario",
            "subtotal",
            "compra",
            "producto",
            "producto_nombre",
        ]

class DetalleNuevaCompraSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.filter(estado=True)
    )
    cantidad = serializers.IntegerField(min_value=1)
    precio_unitario = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00")
    )


class CrearCompraSerializer(serializers.Serializer):
    proveedor = serializers.PrimaryKeyRelatedField(
        queryset=Proveedor.objects.filter(estado=True)
    )

    numero_factura = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        allow_null=True
    )

    observaciones = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True
    )

    detalles = DetalleNuevaCompraSerializer(
        many=True,
        allow_empty=False
    )