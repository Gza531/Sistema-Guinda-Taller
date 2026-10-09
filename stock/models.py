from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Stock(models.Model):

    class Ubicaciones(models.TextChoices):
        SUCURSAL = "SUCURSAL", "Sucursal"
        DEPOSITO = "DEPOSITO", "Depósito"

    id_stock = models.AutoField(
        primary_key=True
    )

    cantidad_actual = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )

    stock_minimo = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )

    ultima_actualizacion = models.DateTimeField(
        auto_now=True
    )

    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        db_column="id_producto"
    )

    ubicacion = models.CharField(
        max_length=50,
        choices=Ubicaciones.choices
    )

    class Meta:
        db_table = "stock"

        constraints = [
            models.UniqueConstraint(
                fields=["producto", "ubicacion"],
                name="unique_producto_ubicacion"
            )
        ]

    def __str__(self):
        return f"{self.producto} - {self.ubicacion} - Stock: {self.cantidad_actual}"


class MovimientoStock(models.Model):

    class Movimientos(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SALIDA = "SALIDA", "Salida"
        AJUSTE = "AJUSTE", "Ajuste"
        REPOSICION = "REPOSICION", "Reposición"

    id_movimiento_stock = models.AutoField(
        primary_key=True
    )

    fecha = models.DateTimeField(
        auto_now_add=True
    )

    tipo_movimiento = models.CharField(
        max_length=50,
        choices=Movimientos.choices
    )

    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)]
    )

    motivo = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    referencia = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    stock = models.ForeignKey(
        Stock,
        on_delete=models.PROTECT,
        db_column="id_stock"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario"
    )

    compra = models.ForeignKey(
        "compras.Compra",
        on_delete=models.PROTECT,
        db_column="id_compra",
        null=True,
        blank=True
    )

    venta = models.ForeignKey(
        "ventas.Venta",
        on_delete=models.PROTECT,
        db_column="id_venta",
        null=True,
        blank=True
    )

    class Meta:
        db_table = "movimientos_stock"

        constraints = [
            models.CheckConstraint(
                check=~(
                 models.Q(compra__isnull=False)
                 & models.Q(venta__isnull=False)
             ),
                name="movimiento_stock_no_compra_y_venta"
         ),

            models.CheckConstraint(
                check=(
                 ~models.Q(tipo_movimiento__in=["AJUSTE", "REPOSICION"])
                    | (
                     models.Q(compra__isnull=True)
                        & models.Q(venta__isnull=True)
                    )
                ),
                name="ajuste_reposicion_sin_compra_venta"
            )
            ]
    def __str__(self):
        return f"{self.tipo_movimiento} - {self.stock.producto.nombre} - {self.cantidad}"