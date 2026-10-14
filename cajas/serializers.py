from rest_framework import serializers

from .models import MetodoPago, Caja


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
        

class CajaSerializer(serializers.ModelSerializer):
    tipo_caja_nombre = serializers.CharField(source="get_tipo_caja_display", read_only=True)

    class Meta:
        model = Caja
        fields = [
            "id_caja", "nombre", "tipo_caja", "tipo_caja_nombre",
            "descripcion", "estado", "fecha_registro",
        ]
        read_only_fields = ["fecha_registro"]
        extra_kwargs = {"nombre": {"validators": []}}

    def validate_nombre(self, valor):
        valor = valor.strip()
        repetidas = Caja.objects.filter(nombre__iexact=valor)
        if self.instance:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError("Ya existe una caja con ese nombre.")
        return valor