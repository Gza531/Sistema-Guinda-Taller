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
    # Contacto del cliente: Envíos los muestra al armar el envío de la venta
    cliente_telefono = serializers.CharField(source="cliente.telefono", read_only=True, allow_null=True)
    cliente_direccion = serializers.CharField(source="cliente.direccion", read_only=True, allow_null=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)
    detalles = DetalleVentaSerializer(source="detalleventa_set", many=True, read_only=True)
    pagos = PagoVentaSerializer(source="movimientocaja_set", many=True, read_only=True)
    envios = EnvioDeVentaSerializer(source="envio_set", many=True, read_only=True)

    class Meta:
        model = Venta
        fields = [
            "id_venta", "numero_comprobante", "fecha", "tipo", "estado", "total",
            "cliente", "cliente_nombre", "cliente_telefono", "cliente_direccion",
            "usuario", "usuario_username",
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
    marca_nombre = serializers.CharField(source="producto.marca.nombre", read_only=True)
    volumen = serializers.CharField(source="producto.volumen", read_only=True)
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = DetalleVenta
        fields = ["producto", "producto_nombre", "marca_nombre", "volumen", "imagen",
                  "cantidad", "precio_unitario", "descuento_aplicado", "subtotal"]
        read_only_fields = fields

    def get_imagen(self, detalle):
        """URL de la foto principal (la misma que muestra la tienda), o None si no tiene fotos."""
        imagenes = list(detalle.producto.imagenes.all())  # viene del prefetch de la vista
        if not imagenes:
            return None
        principal = next((imagen for imagen in imagenes if imagen.es_principal), imagenes[0])
        request = self.context.get("request")
        url = principal.imagen.url
        return request.build_absolute_uri(url) if request else url


class MiCompraSerializer(serializers.ModelSerializer):
    """Listado: lo justo para la tarjeta de cada compra."""
    estado_texto = serializers.CharField(source="get_estado_display", read_only=True)
    cantidad_productos = serializers.SerializerMethodField()
    envio = serializers.SerializerMethodField()
    metodos_pago = serializers.SerializerMethodField()

    class Meta:
        model = Venta
        fields = ["id_venta", "numero_comprobante", "fecha", "tipo", "estado", "estado_texto",
                  "total", "cantidad_productos", "envio", "metodos_pago"]
        read_only_fields = fields

    def get_cantidad_productos(self, venta):
        return sum(detalle.cantidad for detalle in venta.detalleventa_set.all())

    def get_envio(self, venta):
        # Un solo envío activo por venta (si uno vuelve "Devuelto" se puede crear otro):
        # la vista los ordena del más nuevo al más viejo, así que el primero es el vigente.
        # Sin envío = retiro en el local (o venta en el local).
        envios = venta.envio_set.all()
        return MiEnvioSerializer(envios[0]).data if envios else None

    def get_metodos_pago(self, venta):
        # Con qué pagó el cliente: los métodos de los cobros (ingresos) de la venta,
        # sin repetir. Si se anuló, los egresos de la devolución no se cuentan.
        # La vista los trae ya filtrados y ordenados en "cobros".
        cobros = getattr(venta, "cobros", None)
        if cobros is None:
            cobros = (venta.movimientocaja_set
                      .filter(tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO)
                      .select_related("metodo_pago").order_by("id_movimiento_caja"))
        nombres = []
        for movimiento in cobros:
            if movimiento.metodo_pago.nombre not in nombres:
                nombres.append(movimiento.metodo_pago.nombre)
        return nombres


class MiCompraDetalleSerializer(MiCompraSerializer):
    """Detalle: lo mismo que el listado, más los productos comprados."""
    detalles = MiDetalleCompraSerializer(source="detalleventa_set", many=True, read_only=True)

    class Meta(MiCompraSerializer.Meta):
        fields = MiCompraSerializer.Meta.fields + ["detalles"]
        read_only_fields = fields    