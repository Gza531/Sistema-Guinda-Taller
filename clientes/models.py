from django.conf import settings
from django.db import models


class Cliente(models.Model):

    class TipoDocumento(models.TextChoices):
        DNI = "DNI", "DNI"
        CUIT = "CUIT", "CUIT"
        CUIL = "CUIL", "CUIL"

    id_cliente = models.AutoField(
        primary_key=True
    )

    nombre = models.CharField(
        max_length=60
    )

    apellido = models.CharField(
        max_length=60
    )

    tipo_documento = models.CharField(
        max_length=4,
        choices=TipoDocumento.choices,
        null=True,
        blank=True
    )

    nro_documento = models.CharField(
        max_length=13,
        unique=True,
        null=True,
        blank=True
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

    fecha_alta = models.DateField(
        auto_now_add=True
    )

    estado = models.BooleanField(
        default=True
    )

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        db_column="id_usuario",
        null=True,
        blank=True
    )

    class Meta:
        db_table = "clientes"

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    # Cliente genérico para ventas sin cliente identificado (RN-03).
    # Lo crea la migración 0003_consumidor_final de esta app.
    CF_NOMBRE = "Consumidor"
    CF_APELLIDO = "Final"

    @classmethod
    def consumidor_final(cls):
        return cls.objects.filter(
            nombre=cls.CF_NOMBRE, apellido=cls.CF_APELLIDO, nro_documento__isnull=True
        ).order_by("id_cliente").first()

    @property
    def es_consumidor_final(self):
        return self.pk == Cliente.consumidor_final().pk
