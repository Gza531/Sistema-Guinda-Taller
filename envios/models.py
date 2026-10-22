from django.core.validators import MinValueValidator
from django.db import models


class Envio(models.Model):

    class EstadoEnvio(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PREPARADO = "PREPARADO", "Preparado"
        DESPACHADO = "DESPACHADO", "Despachado"
        EN_TRANSITO = "EN_TRANSITO", "En tránsito"
        ENTREGADO = "ENTREGADO", "Entregado"
        DEMORADO = "DEMORADO", "Demorado"
        DEVUELTO = "DEVUELTO", "Devuelto"
        CANCELADO = "CANCELADO", "Cancelado"

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
        "ventas.Venta",
        on_delete=models.PROTECT,
        db_column="id_venta"
    )

    class Meta:
        db_table = "envios"

    def __str__(self):
        return f"Envío {self.id_envio} - Venta {self.venta.numero_comprobante}"
