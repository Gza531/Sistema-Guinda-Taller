from rest_framework import serializers

from catalogo.models import Producto
from .models import MovimientoStock, Stock


class StockSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = Stock
        fields = [
            "id_stock",
            "producto",
            "producto_nombre",
            "ubicacion",
            "cantidad_actual",
            "stock_minimo",
            "ultima_actualizacion",
        ]
        read_only_fields = ["cantidad_actual", "ultima_actualizacion"]


class MovimientoStockSerializer(serializers.ModelSerializer):
    """Para MOSTRAR el historial de movimientos."""

    producto_nombre = serializers.CharField(source="stock.producto.nombre", read_only=True)
    ubicacion = serializers.CharField(source="stock.ubicacion", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = MovimientoStock
        fields = [
            "id_movimiento_stock",
            "fecha",
            "tipo_movimiento",
            "cantidad",
            "producto_nombre",
            "ubicacion",
            "motivo",
            "usuario_username",
        ]


class NuevoMovimientoSerializer(serializers.Serializer):
    """
    Para RECIBIR los datos de un movimiento nuevo desde React.
    En una REPOSICION, 'ubicacion' es desde dónde SALE la mercadería.
    """

    TIPOS = [
        ("ENTRADA", "Entrada"),
        ("SALIDA", "Salida"),
        ("REPOSICION", "Reposición / traslado"),
    ]

    tipo_movimiento = serializers.ChoiceField(choices=TIPOS)
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.filter(estado=True))
    ubicacion = serializers.ChoiceField(choices=Stock.Ubicaciones.choices)
    cantidad = serializers.IntegerField(min_value=1)
    motivo = serializers.CharField(max_length=200, required=False, allow_blank=True)