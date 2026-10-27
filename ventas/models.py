from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


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
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario"
    )

    pedido = models.ForeignKey(
        "pedidos.Pedido",
        on_delete=models.SET_NULL,
        db_column="id_pedido",
        null=True,
        blank=True
    )

    # ID del pago en Mercado Pago (solo ventas cobradas desde la tienda web).
    # Único: si Mercado Pago avisa dos veces el mismo pago, no se registran dos ventas.
    # NULL en las demás ventas (PostgreSQL permite muchos NULL en un campo único).
    mp_payment_id = models.CharField(
        max_length=30,
        unique=True,
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
