from rest_framework import serializers

from catalogo.models import Producto
from pedidos.reservas import reservadas
from .models import MovimientoStock, Stock


class StockSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    ultima_entrada = serializers.SerializerMethodField()
    # Depósito: unidades apartadas para pedidos y las que quedan libres para vender o trasladar
    reservado = serializers.SerializerMethodField()
    disponible = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = [
            "id_stock",
            "producto",
            "producto_nombre",
            "ubicacion",
            "cantidad_actual",
            "reservado",
            "disponible",
            "stock_minimo",
            "ultima_actualizacion",
            "ultima_entrada"
        ]
        read_only_fields = ["producto", "ubicacion", "cantidad_actual", "ultima_actualizacion"]
        extra_kwargs = {"stock_minimo": {"min_value": 0}}

    def get_reservado(self, stock):
        valor = getattr(stock, "reservado", None)
        if valor is None:   # sin la anotación de StockViewSet (ej. después de un PATCH)
            valor = reservadas(stock.producto) if stock.ubicacion == Stock.Ubicaciones.DEPOSITO else 0
            stock.reservado = valor
        return valor

    def get_disponible(self, stock):
        return max(0, stock.cantidad_actual - self.get_reservado(stock))

    def get_ultima_entrada(self, stock):
        """
        Cuánto entró en el último movimiento, si ese movimiento fue una ENTRADA
        (el panel lo muestra en verde: 14 +5). Si fue otra cosa o no hubo, None.
        Los datos vienen anotados por StockViewSet.get_queryset.
        """
        if getattr(stock, "ultimo_tipo", None) == MovimientoStock.Movimientos.ENTRADA:
            return stock.ultima_cantidad
        return None


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