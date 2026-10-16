from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser


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
