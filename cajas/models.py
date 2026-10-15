from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone


class Caja(models.Model):

    class TipoCaja(models.TextChoices):
        PRESENCIAL = "PRESENCIAL", "Presencial"
        ONLINE = "ONLINE", "Online"

    id_caja = models.AutoField(
        primary_key=True
    )

    nombre = models.CharField(
        max_length=50,
        unique=True
    )

    tipo_caja = models.CharField(
        max_length=20,
        choices=TipoCaja.choices
    )

    estado = models.BooleanField(
        default=True
    )

    fecha_registro = models.DateField(
        auto_now_add=True
    )

    descripcion = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    class Meta:
        db_table = "cajas"

    def __str__(self):
        return self.nombre


class AperturaCierreCaja(models.Model):

    id_apertura_cierre = models.AutoField(
        primary_key=True
    )

    caja = models.ForeignKey(
        Caja,
        on_delete=models.PROTECT,
        db_column="id_caja"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario"
    )

    fecha_apertura = models.DateTimeField(
        auto_now_add=True
    )

    fecha_cierre = models.DateTimeField(
        null=True,
        blank=True
    )

    monto_inicial = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    monto_final = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )

    observaciones = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    class Meta:
        db_table = "apertura_cierre_cajas"

    def __str__(self):
        fecha = timezone.localtime(self.fecha_apertura).strftime("%d/%m/%Y %H:%M")
        estado = "Abierta" if self.fecha_cierre is None else "Cerrada"
        return f"{self.caja.nombre} - {estado} - {fecha}"

class MetodoPago(models.Model):

    id_metodo_pago = models.AutoField(
        primary_key=True
    )

    nombre = models.CharField(
        max_length=50,
        unique=True
    )

    estado = models.BooleanField(
        default=True
    )

    class Meta:
        db_table = "metodos_pago"

    def __str__(self):
        return self.nombre

    EFECTIVO = "Efectivo"

    @classmethod
    def efectivo(cls):
        return cls.objects.get(nombre=cls.EFECTIVO)

    @property
    def es_efectivo(self):
        return self.nombre == self.EFECTIVO


class MovimientoCaja(models.Model):

    class TipoMovimiento(models.TextChoices):
        INGRESO = "INGRESO", "Ingreso"
        EGRESO = "EGRESO", "Egreso"

    id_movimiento_caja = models.AutoField(
        primary_key=True
    )

    fecha_hora = models.DateTimeField(
        auto_now_add=True
    )

    tipo_movimiento = models.CharField(
        max_length=20,
        choices=TipoMovimiento.choices
    )

    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    concepto = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    apertura_cierre = models.ForeignKey(
        AperturaCierreCaja,
        on_delete=models.PROTECT,
        db_column="id_apertura_cierre"
    )

    metodo_pago = models.ForeignKey(
        MetodoPago,
        on_delete=models.PROTECT,
        db_column="id_metodo_pago"
    )

    venta = models.ForeignKey(
        "ventas.Venta",
        on_delete=models.PROTECT,
        db_column="id_venta",
        null=True,
        blank=True
    )

    compra = models.ForeignKey(
        "compras.Compra",
        on_delete=models.PROTECT,
        db_column="id_compra",
        null=True,
        blank=True
    )

    class Meta:
        db_table = "movimientos_caja"

        constraints = [
            models.CheckConstraint(
                check=~(
                    models.Q(venta__isnull=False)
                    & models.Q(compra__isnull=False)
                ),
                name="movimiento_caja_no_venta_y_compra"
            )
        ]

    def __str__(self):
        fecha = timezone.localtime(self.fecha_hora).strftime("%d/%m/%Y %H:%M")
        return f"{self.tipo_movimiento} - ${self.monto} - {fecha}"