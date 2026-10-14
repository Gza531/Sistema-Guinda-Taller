from rest_framework import serializers

from .models import MetodoPago


class MetodoPagoSerializer(serializers.ModelSerializer):
    """Convierte un MetodoPago a JSON (para responder) y valida el JSON que llega (para crear o editar)."""
    def validate_nombre(self, valor):
        valor = valor.strip()
        repetidos = MetodoPago.objects.filter(nombre__iexact=valor)
        if self.instance:  # al editar, no compararse consigo mismo
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError("Ya existe un método de pago con ese nombre.")
        return valor
    
    class Meta:
        model = MetodoPago
        fields = ["id_metodo_pago", "nombre", "estado"]