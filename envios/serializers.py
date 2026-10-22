from decimal import Decimal

from rest_framework import serializers

from ventas.models import Venta

from .models import Envio

class EnvioSerializer(serializers.ModelSerializer):
    venta_comprobante = serializers.CharField(
        source="venta.numero_comprobante",
        read_only=True
    )

    cliente_nombre = serializers.CharField(
        source="venta.cliente.__str__",
        read_only=True
    )

    class Meta:
        model = Envio

        fields = [
            "id_envio",
            "venta",
            "venta_comprobante",
            "cliente_nombre",
            "direccion_entrega",
            "costo",
            "empresa_transporte",
            "codigo_seguimiento",
            "estado",
            "fecha_despacho",
        ]

        read_only_fields = fields


class NuevoEnvioSerializer(serializers.Serializer):
    venta = serializers.PrimaryKeyRelatedField(
        queryset=Venta.objects.all()
    )

    direccion_entrega = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True
    )

    costo = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True
    )

    empresa_transporte = serializers.CharField(
        max_length=80,
        required=False,
        allow_blank=True
    )

    codigo_seguimiento = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True
    )


class EditarEnvioSerializer(serializers.Serializer):
    direccion_entrega = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True
    )

    costo = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True
    )

    empresa_transporte = serializers.CharField(
        max_length=80,
        required=False,
        allow_blank=True
    )

    codigo_seguimiento = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True
    )


class CambiarEstadoEnvioSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(
        choices=Envio.EstadoEnvio.choices
    )

    empresa_transporte = serializers.CharField(
        max_length=80,
        required=False,
        allow_blank=True
    )

    codigo_seguimiento = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True
    )
