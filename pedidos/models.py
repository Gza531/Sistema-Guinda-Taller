from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


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
        "clientes.Cliente",
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
