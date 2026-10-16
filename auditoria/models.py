from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


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


    def __str__(self):
        fecha = timezone.localtime(self.fecha_hora).strftime("%d/%m/%Y %H:%M")
        return f"{self.accion} - {self.tabla_afectada} - {fecha}"
