from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


class Promocion(models.Model):

    class TipoDescuento(models.TextChoices):
        PORCENTAJE = "PORCENTAJE", "Porcentaje"
        MONTO_FIJO = "MONTO_FIJO", "Monto fijo"

    id_promocion = models.AutoField(
        primary_key=True
    )

    nombre = models.CharField(
        max_length=80
    )

    descripcion = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    tipo_descuento = models.CharField(
        max_length=20,
        choices=TipoDescuento.choices
    )

    valor_descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    fecha_inicio = models.DateField()

    fecha_fin = models.DateField()

    estado = models.BooleanField(
        default=True
    )

    class Meta:
        db_table = "promociones"

    def clean(self):
        super().clean()

        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_fin < self.fecha_inicio:
                raise ValidationError(
                    "La fecha de fin no puede ser anterior a la fecha de inicio."
                )

        if (
            self.tipo_descuento == self.TipoDescuento.PORCENTAJE
            and self.valor_descuento > 100
        ):
            raise ValidationError(
                "Un descuento porcentual no puede ser mayor a 100%."
            )

    def __str__(self):
        return self.nombre


class PromocionProducto(models.Model):

    id_promocion_producto = models.AutoField(
        primary_key=True
    )

    promocion = models.ForeignKey(
        Promocion,
        on_delete=models.CASCADE,
        db_column="id_promocion"
    )

    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        db_column="id_producto"
    )

    class Meta:
        db_table = "promocion_productos"

        constraints = [
            models.UniqueConstraint(
                fields=["promocion", "producto"],
                name="unique_promocion_producto"
            )
        ]

    def __str__(self):
        return f"{self.promocion} - {self.producto}"