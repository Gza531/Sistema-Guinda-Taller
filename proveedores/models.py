from django.core.validators import MinValueValidator
from django.db import models


class Proveedor(models.Model):

    id_proveedor = models.AutoField(
        primary_key=True
    )

    razon_social = models.CharField(
        max_length=120
    )

    cuit = models.CharField(
        max_length=13,
        unique=True
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

    observaciones = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    estado = models.BooleanField(
        default=True
    )

    class Meta:
        db_table = "proveedores"

    def __str__(self):
        return self.razon_social


class ProveedorXProducto(models.Model):

    id_proveedor_producto = models.AutoField(
        primary_key=True
    )

    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        db_column="id_proveedor"
    )

    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        db_column="id_producto"
    )

    precio_compra_referencia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    codigo_producto_proveedor = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    observaciones = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    class Meta:
        db_table = "proveedores_x_productos"

        constraints = [
            models.UniqueConstraint(
                fields=["proveedor", "producto"],
                name="unique_proveedor_producto"
            )
        ]

    def __str__(self):
        return f"{self.proveedor} - {self.producto}"
