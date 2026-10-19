from django.db import models
from django.core.validators import MinValueValidator


class Marca(models.Model):

    id_marca = models.AutoField(
        primary_key=True
    )

    nombre = models.CharField(
        max_length=80,
        unique=True
    )

    descripcion = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    estado = models.BooleanField(
        default=True
    )

    class Meta:
        db_table = "marcas"

    def __str__(self):
        return self.nombre


class Categoria(models.Model):

    id_categoria = models.AutoField(
        primary_key=True
    )

    nombre = models.CharField(
        max_length=80,
        unique=True
    )

    descripcion = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    estado = models.BooleanField(
        default=True
    )

    class Meta:
        db_table = "categorias"

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

    id_producto = models.AutoField(
        primary_key=True
    )

    version_producto = models.CharField(
        max_length=20,
        choices=VersionProducto.choices,
        default=VersionProducto.ORIGINAL
    )

    nombre = models.CharField(
        max_length=120
    )

    descripcion = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    volumen = models.CharField(
        max_length=60,
        null=True,
        blank=True
    )

    genero_producto = models.CharField(
        max_length=20,
        choices=GeneroProducto.choices,
        null=True,
        blank=True
    )

    origen = models.CharField(
        max_length=20,
        choices=OrigenProducto.choices
    )

    precio_venta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    fecha_alta = models.DateField(
        auto_now_add=True
    )

    estado = models.BooleanField(
        default=True
    )


    marca = models.ForeignKey(
        Marca,
        on_delete=models.PROTECT,
        db_column="id_marca"
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        db_column="id_categoria"
    )

    class Meta:
        db_table = "productos"

    def __str__(self):
        return self.nombre



class ImagenProducto(models.Model):

    id_imagen_producto = models.AutoField(
        primary_key=True
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        db_column="id_producto",
        related_name="imagenes"
    )

    imagen = models.ImageField(
        upload_to="productos/%Y/%m/"
    )

    orden = models.PositiveSmallIntegerField(
        default=0
    )

    es_principal = models.BooleanField(
        default=False
    )

    fecha_alta = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = "imagenes_productos"
        ordering = ["orden", "id_imagen_producto"]

        constraints = [
            # A lo sumo una imagen principal por producto
            models.UniqueConstraint(
                fields=["producto"],
                condition=models.Q(es_principal=True),
                name="una_imagen_principal_por_producto"
            )
        ]

    def __str__(self):
        return f"Imagen {self.orden} de {self.producto}"