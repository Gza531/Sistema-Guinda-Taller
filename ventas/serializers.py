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