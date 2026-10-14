from rest_framework import serializers

from .models import MetodoPago


class MetodoPagoSerializer(serializers.ModelSerializer):
    """Convierte un MetodoPago a JSON (para responder) y valida el JSON que llega (para crear o editar)."""

    class Meta:
        model = MetodoPago
        fields = ["id_metodo_pago", "nombre", "estado"]