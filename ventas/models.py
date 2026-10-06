from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Cliente(models.Model):

    class TipoDocumento(models.TextChoices):
        DNI = "DNI", "DNI"
        CUIT = "CUIT", "CUIT"
        CUIL = "CUIL", "CUIL"

    id_cliente = models.AutoField(
        primary_key=True
    )

    nombre = models.CharField(
        max_length=60
    )

    apellido = models.CharField(
        max_length=60
    )

    tipo_documento = models.CharField(
        max_length=4,
        choices=TipoDocumento.choices,
        null=True,
        blank=True
    )

    nro_documento = models.CharField(
        max_length=13,
        unique=True,
        null=True,
        blank=True
    )

    telefono = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    email = models.EmailField(
        max_length=100,
        null=True,
        blank=True
    )

    direccion = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    fecha_alta = models.DateField(
        auto_now_add=True
    )

    estado = models.BooleanField(
        default=True
    )

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        db_column="id_usuario",
        null=True,
        blank=True
    )

    class Meta:
        db_table = "clientes"

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

class Pedido(models.Model):

    class Canal(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        PRESENCIAL = "PRESENCIAL", "Presencial"
        ML = "ML", "Mercado Libre"
        WEB = "WEB", "Web"
        OTRO = "OTRO", "Otro"

    class EstadoPedido(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        RESERVADO = "RESERVADO", "Reservado"
        EN_ESPERA_STOCK = "EN_ESPERA_STOCK", "En espera de stock"
        LISTO = "LISTO", "Listo"
        ENTREGADO = "ENTREGADO", "Entregado"
        CANCELADO = "CANCELADO", "Cancelado"

    id_pedido = models.AutoField(
        primary_key=True
    )

    fecha = models.DateTimeField(
        auto_now_add=True
    )

    canal = models.CharField(
        max_length=20,
        choices=Canal.choices
    )

    estado = models.CharField(
        max_length=20,
        choices=EstadoPedido.choices,
        default=EstadoPedido.PENDIENTE
    )

    observaciones = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        db_column="id_cliente"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        db_column="id_usuario",
        null=True,
        blank=True
    )

    class Meta:
        db_table = "pedidos"

    def __str__(self):
        return f"Pedido {self.id_pedido} - {self.cliente}"

class DetallePedido(models.Model):

    id_detalle_pedido = models.AutoField(
        primary_key=True
    )

    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)]
    )

    precio_referencia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        db_column="id_pedido"
    )

    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        db_column="id_producto"
    )

    class Meta:
        db_table = "detalles_pedidos"

    def __str__(self):
        return f"Detalle {self.id_detalle_pedido} - {self.producto}"


class Venta(models.Model):

    class TipoVenta(models.TextChoices):
        PRESENCIAL = "PRESENCIAL", "Presencial"
        ONLINE = "ONLINE", "Online"

    class EstadoVenta(models.TextChoices):
        REGISTRADA = "REGISTRADA", "Registrada"
        ANULADA = "ANULADA", "Anulada"

    id_venta = models.AutoField(
        primary_key=True
    )

    fecha = models.DateTimeField(
        auto_now_add=True
    )

    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    tipo = models.CharField(
        max_length=20,
        choices=TipoVenta.choices
    )

    estado = models.CharField(
        max_length=20,
        choices=EstadoVenta.choices,
        default=EstadoVenta.REGISTRADA
    )

    observaciones = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        db_column="id_cliente"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario"
    )

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.SET_NULL,
        db_column="id_pedido",
        null=True,
        blank=True
    )

    numero_comprobante = models.CharField(
        max_length=20,
        unique=True
    )

    class Meta:
        db_table = "ventas"

    def __str__(self):
        return f"Venta {self.numero_comprobante}"

class DetalleVenta(models.Model):

    id_detalle_venta = models.AutoField(
        primary_key=True
    )

    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)]
    )

    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    descuento_aplicado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        db_column="id_venta"
    )

    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        db_column="id_producto"
    )

    class Meta:
        db_table = "detalles_ventas"

    def __str__(self):
        return f"Detalle {self.id_detalle_venta} - {self.producto}"
    

class Envio(models.Model):

    class EstadoEnvio(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PREPARADO = "PREPARADO", "Preparado"
        DESPACHADO = "DESPACHADO", "Despachado"
        EN_TRANSITO = "EN_TRANSITO", "En tránsito"
        ENTREGADO = "ENTREGADO", "Entregado"
        DEMORADO = "DEMORADO", "Demorado"
        DEVUELTO = "DEVUELTO", "Devuelto"

    id_envio = models.AutoField(
        primary_key=True
    )

    fecha_despacho = models.DateTimeField(
        null=True,
        blank=True
    )

    empresa_transporte = models.CharField(
        max_length=80,
        null=True,
        blank=True
    )

    codigo_seguimiento = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    direccion_entrega = models.CharField(
        max_length=200
    )

    estado = models.CharField(
        max_length=20,
        choices=EstadoEnvio.choices,
        default=EstadoEnvio.PENDIENTE
    )

    costo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )

    venta = models.ForeignKey(
        Venta,
        on_delete=models.PROTECT,
        db_column="id_venta"
    )

    class Meta:
        db_table = "envios"

    def __str__(self):
        return f"Envío {self.id_envio} - Venta {self.venta.numero_comprobante}"