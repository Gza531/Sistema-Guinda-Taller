from decimal import Decimal

from rest_framework import serializers

from cajas.models import Caja, MetodoPago, MovimientoCaja
from catalogo.models import Producto
from clientes.models import Cliente
from envios.models import Envio

from .models import DetalleVenta, Venta
from .services import Entrega


# ---------------- Lectura ----------------

class DetalleVentaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = DetalleVenta
        fields = [
            "producto", "producto_nombre", "cantidad",
            "precio_unitario", "descuento_aplicado", "subtotal",
        ]


class PagoVentaSerializer(serializers.ModelSerializer):
    metodo_pago_nombre = serializers.CharField(source="metodo_pago.nombre", read_only=True)

    class Meta:
        model = MovimientoCaja
        fields = ["metodo_pago", "metodo_pago_nombre", "monto", "tipo_movimiento"]


class EnvioDeVentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Envio
        fields = ["id_envio", "estado", "direccion_entrega", "costo",
                  "empresa_transporte", "codigo_seguimiento"]


class VentaSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source="cliente.__str__", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)
    detalles = DetalleVentaSerializer(source="detalleventa_set", many=True, read_only=True)
    pagos = PagoVentaSerializer(source="movimientocaja_set", many=True, read_only=True)
    envios = EnvioDeVentaSerializer(source="envio_set", many=True, read_only=True)

    class Meta:
        model = Venta
        fields = [
            "id_venta", "numero_comprobante", "fecha", "tipo", "estado", "total",
            "cliente", "cliente_nombre", "usuario", "usuario_username",
            "observaciones", "pedido","mp_payment_id", "detalles", "pagos", "envios",
        ]
        read_only_fields = fields


# ---------------- Escritura (venta presencial) ----------------

class ItemVentaSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.filter(estado=True))
    cantidad = serializers.IntegerField(min_value=1)


class PagoSerializer(serializers.Serializer):
    metodo_pago = serializers.PrimaryKeyRelatedField(queryset=MetodoPago.objects.all())
    monto = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class NuevaVentaSerializer(serializers.Serializer):
    caja = serializers.PrimaryKeyRelatedField(queryset=Caja.objects.filter(estado=True))
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.filter(estado=True), required=False, allow_null=True
    )
    items = ItemVentaSerializer(many=True, allow_empty=False)
    pagos = PagoSerializer(many=True, allow_empty=False)
    observaciones = serializers.CharField(max_length=500, required=False, allow_blank=True)

class AnularVentaSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=250)


# ---------------- Escritura (venta online) ----------------

class NuevaVentaOnlineSerializer(serializers.Serializer):
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.filter(estado=True))
    items = ItemVentaSerializer(many=True, allow_empty=False)
    pagos = PagoSerializer(many=True, allow_empty=False)
    entrega = serializers.ChoiceField(choices=Entrega.choices)
    direccion_entrega = serializers.CharField(max_length=200, required=False, allow_blank=True)
    costo_envio = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True
    )
    observaciones = serializers.CharField(max_length=500, required=False, allow_blank=True)

# ---------------- Mis compras (tienda web: lo que ve el cliente) ----------------
# Solo datos que le sirven al cliente: nada de usuario, caja, observaciones
# internas ni id de Mercado Pago.

class MiEnvioSerializer(serializers.ModelSerializer):
    estado_texto = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = Envio
        fields = ["estado", "estado_texto", "empresa_transporte", "codigo_seguimiento",
                  "fecha_despacho", "direccion_entrega", "costo"]
        read_only_fields = fields


class MiDetalleCompraSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = DetalleVenta
        fields = ["producto", "producto_nombre", "cantidad", "precio_unitario",
                  "descuento_aplicado", "subtotal"]
        read_only_fields = fields


class MiCompraSerializer(serializers.ModelSerializer):
    """Listado: lo justo para la tarjeta de cada compra."""
    estado_texto = serializers.CharField(source="get_estado_display", read_only=True)
    cantidad_productos = serializers.SerializerMethodField()
    envio = serializers.SerializerMethodField()

    class Meta:
        model = Venta
        fields = ["id_venta", "numero_comprobante", "fecha", "tipo", "estado", "estado_texto",
                  "total", "cantidad_productos", "envio"]
        read_only_fields = fields

    def get_cantidad_productos(self, venta):
        return sum(detalle.cantidad for detalle in venta.detalleventa_set.all())

    def get_envio(self, venta):
        # Una venta tiene a lo sumo un envío; si no tiene, es retiro en el local (o venta en el local)
        envios = venta.envio_set.all()
        return MiEnvioSerializer(envios[0]).data if envios else None


class MiCompraDetalleSerializer(MiCompraSerializer):
    """Detalle: lo mismo que el listado, más los productos comprados."""
    detalles = MiDetalleCompraSerializer(source="detalleventa_set", many=True, read_only=True)

    class Meta(MiCompraSerializer.Meta):
        fields = MiCompraSerializer.Meta.fields + ["detalles"]
        read_only_fields = fields    