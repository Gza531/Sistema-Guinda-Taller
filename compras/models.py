from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Compra(models.Model):

    class EstadoCompra(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        RECIBIDA = "RECIBIDA", "Recibida"
        ANULADA = "ANULADA", "Anulada"

    id_compra = models.AutoField(
        primary_key=True
    )

    fecha = models.DateTimeField(
        auto_now_add=True
    )

    numero_factura = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    estado = models.CharField(
        max_length=20,
        choices=EstadoCompra.choices,
        default=EstadoCompra.PENDIENTE
    )

    observaciones = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    proveedor = models.ForeignKey(
        "proveedores.Proveedor",
        on_delete=models.PROTECT,
        db_column="id_proveedor"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario"
    )

    class Meta:
        db_table = "compras"

    def __str__(self):
        return f"Compra {self.id_compra} - {self.proveedor}"


class DetalleCompra(models.Model):

    id_detalle_compra = models.AutoField(
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

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    compra = models.ForeignKey(
        Compra,
        on_delete=models.CASCADE,
        db_column="id_compra"
    )

    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        db_column="id_producto"
    )

    class Meta:
        db_table = "detalles_compras"

    def __str__(self):
        return f"Detalle {self.id_detalle_compra} - {self.producto}"
