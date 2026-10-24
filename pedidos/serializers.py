from decimal import Decimal

from rest_framework import serializers

from catalogo.models import Producto
from clientes.models import Cliente

from .models import DetallePedido, Pedido
from ventas.serializers import PagoSerializer
from ventas.services import Entrega


class DetallePedidoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(
        source="producto.nombre",
        read_only=True
    )

    subtotal = serializers.SerializerMethodField()

    def get_subtotal(self, obj):
        return str(obj.precio_referencia * obj.cantidad)

    class Meta:
        model = DetallePedido
        fields = [
            "producto",
            "producto_nombre",
            "cantidad",
            "precio_referencia",
            "subtotal"
        ]

class PedidoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(
        source="cliente.__str__",
        read_only=True
    )

    usuario_username = serializers.CharField(
        source="usuario.username",
        read_only=True,
        default=None
    )

    detalles = DetallePedidoSerializer(
        source="detallepedido_set",
        many=True,
        read_only=True
    )

    total_referencia = serializers.SerializerMethodField()

    ventas = serializers.PrimaryKeyRelatedField(
        source="venta_set",
        many=True,
        read_only=True
    )

    def get_total_referencia(self, obj):
        total = sum(
            (
                detalle.precio_referencia * detalle.cantidad
                for detalle in obj.detallepedido_set.all()
            ),
            Decimal("0.00")
        )
        return str(total)

    class Meta:
        model = Pedido
        fields = [
            "id_pedido",
            "fecha",
            "canal",
            "estado",
            "observaciones",
            "cliente",
            "cliente_nombre",
            "usuario",
            "usuario_username",
            "detalles",
            "total_referencia",
            "ventas"
        ]
        read_only_fields = fields

class ItemPedidoSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.filter(estado=True)
    )

    cantidad = serializers.IntegerField(min_value=1)

class NuevoPedidoSerializer(serializers.Serializer):
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.filter(estado=True)
    )

    canal = serializers.ChoiceField(
        choices=Pedido.Canal.choices
    )

    items = ItemPedidoSerializer(
        many=True,
        allow_empty=False
    )

    observaciones = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
class CambiarEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(
        choices=Pedido.EstadoPedido.choices
    )

class CancelarPedidoSerializer(serializers.Serializer):
    motivo = serializers.CharField(
        max_length=250
    )

class EntregarPedidoSerializer(serializers.Serializer):
    pagos = PagoSerializer(
        many=True,
        allow_empty=False
    )

    entrega = serializers.ChoiceField(
        choices=Entrega.choices
    )

    direccion_entrega = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True
    )

    costo_envio = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True
    )
