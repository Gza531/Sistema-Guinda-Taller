from rest_framework import serializers

from .models import AperturaCierreCaja, MetodoPago, Caja
from .services import sesion_abierta

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
    abierta = serializers.SerializerMethodField()

    class Meta:
        model = Caja
        fields = [
            "id_caja", "nombre", "tipo_caja", "tipo_caja_nombre",
            "descripcion", "estado", "fecha_registro", "abierta"
        ]
        read_only_fields = ["fecha_registro"]
        extra_kwargs = {"nombre": {"validators": []}}


    def get_abierta(self, obj):
        return sesion_abierta(obj) is not None

    def validate_nombre(self, valor):
        valor = valor.strip()
        repetidas = Caja.objects.filter(nombre__iexact=valor)
        if self.instance:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError("Ya existe una caja con ese nombre.")
        return valor

class SesionCajaSerializer(serializers.ModelSerializer):
    """Lectura de una sesión de caja (apertura y, si ya cerró, su cierre)."""

    caja_nombre = serializers.CharField(source="caja.nombre", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)
    abierta = serializers.SerializerMethodField()

    class Meta:
        model = AperturaCierreCaja
        fields = [
            "id_apertura_cierre", "caja", "caja_nombre", "usuario", "usuario_username",
            "fecha_apertura", "monto_inicial", "fecha_cierre", "monto_final",
            "observaciones", "abierta",
        ]
        read_only_fields = fields

    def get_abierta(self, obj):
        return obj.fecha_cierre is None


class AbrirCajaSerializer(serializers.Serializer):
    """Datos que manda el frontend para abrir una caja."""

    caja = serializers.PrimaryKeyRelatedField(queryset=Caja.objects.all())
    monto_inicial = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    observaciones = serializers.CharField(max_length=500, required=False, allow_blank=True)