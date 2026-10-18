from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from catalogo.models import Producto
from .models import Promocion, PromocionProducto
from . import services

class ProductoEnPromocionSerializer(serializers.Serializer):
    producto = serializers.IntegerField(
        source="producto.id_producto"
    )

    nombre = serializers.CharField(
        source="producto.nombre"
    )

    precio_venta = serializers.DecimalField(
        source="producto.precio_venta",
        max_digits=12,
        decimal_places=2
    )

    precio_con_descuento = serializers.SerializerMethodField()

    def get_precio_con_descuento(self, obj):
        promocion = self.context["promocion"]
        precio = obj.producto.precio_venta

        descuento = services.monto_descuento(
            promocion,
            precio
        )

        return str(precio - descuento)

class PromocionSerializer(serializers.ModelSerializer):
    vigente = serializers.SerializerMethodField()
    productos = serializers.SerializerMethodField()

    def get_vigente(self, obj):
        hoy = timezone.localdate()

        return (
            obj.estado
            and obj.fecha_inicio <= hoy <= obj.fecha_fin
        )

    def get_productos(self, obj):
        relaciones = obj.promocionproducto_set.all()

        return ProductoEnPromocionSerializer(
            relaciones,
            many=True,
            context={"promocion": obj}
        ).data

    class Meta:
        model = Promocion
        fields = [
            "id_promocion",
            "nombre",
            "descripcion",
            "tipo_descuento",
            "valor_descuento",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "vigente",
            "productos"
        ]

        read_only_fields = fields

class PromocionEntradaSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=80)

    descripcion = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )

    tipo_descuento = serializers.ChoiceField(
        choices=Promocion.TipoDescuento.choices
    )

    valor_descuento = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01")
    )

    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()

    productos = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.filter(estado=True),
        many=True,
        allow_empty=False
    )