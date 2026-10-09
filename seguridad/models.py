from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone


class Usuario(AbstractUser):

    id_usuario = models.AutoField(
        primary_key=True
    )

    class Meta:
        db_table = "usuarios"

    def __str__(self):
        return self.username


class Empleado(models.Model):

    id_empleado = models.AutoField(
        primary_key=True
    )

    nombre = models.CharField(
        max_length=60
    )

    apellido = models.CharField(
        max_length=60
    )

    dni = models.CharField(
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
        unique=True,
        null=True,
        blank=True
    )

    fecha_alta = models.DateTimeField(
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
        db_table = "empleados"

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class Auditoria(models.Model):

    class Accion(models.TextChoices):
        INSERT = "INSERT", "Insert"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"
        LOGIN = "LOGIN", "Login"
        LOGOUT = "LOGOUT", "Logout"

    id_auditoria = models.AutoField(
        primary_key=True
    )

    fecha_hora = models.DateTimeField(
        auto_now_add=True
    )

    accion = models.CharField(
        max_length=10,
        choices=Accion.choices
    )

    tabla_afectada = models.CharField(
        max_length=50
    )

    id_registro_afectado = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        null=True,
        blank=True
    )

    datos_previos = models.TextField(
        null=True,
        blank=True
    )

    datos_nuevos = models.TextField(
        null=True,
        blank=True
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario"
    )

    class Meta:
        db_table = "auditorias"

    from django.utils import timezone

    def __str__(self):
        fecha = timezone.localtime(self.fecha_hora).strftime("%d/%m/%Y %H:%M")
        return f"{self.accion} - {self.tabla_afectada} - {fecha}"