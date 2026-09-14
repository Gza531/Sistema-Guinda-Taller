from django.db import models
from django.core.validators import MinValueValidator


class Marca(models.Model):
    nombre = models.CharField(max_length=120)

    descripcion = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    nombre = models.CharField(max_length=120)

    descripcion = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):

    class VersionProducto(models.TextChoices):
        ORIGINAL = "ORIGINAL", "Original"
        REPLICA = "REPLICA", "Réplica"

    class GeneroProducto(models.TextChoices):
        MASCULINO = "MASCULINO", "Masculino"
        FEMENINO = "FEMENINO", "Femenino"
        UNISEX = "UNISEX", "Unisex"
        NO_APLICA = "NO_APLICA", "No aplica"

    class OrigenProducto(models.TextChoices):
        NACIONAL = "NACIONAL", "Nacional"
        IMPORTADO = "IMPORTADO", "Importado"

    version_producto = models.CharField(
        max_length=20,
        choices=VersionProducto.choices,
        default=VersionProducto.ORIGINAL
    )

    nombre = models.CharField(max_length=120)

    descripcion = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    presentacion = models.CharField(
        max_length=60,
        null=True,
        blank=True
    )

    precio_venta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    fecha_alta = models.DateField(auto_now_add=True)

    estado = models.BooleanField(default=True)

    marca = models.ForeignKey(
        Marca,
        on_delete=models.PROTECT
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT
    )

    precio_costo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    genero_producto = models.CharField(
        max_length=20,
        choices=GeneroProducto.choices,
        null=True,
        blank=True
    )

    origen = models.CharField(
        max_length=20,
        choices=OrigenProducto.choices,
        default=OrigenProducto.NACIONAL
    )

    def __str__(self):
        return self.nombre