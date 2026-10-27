from rest_framework import serializers

from ventas.serializers import ItemVentaSerializer
from ventas.services import Entrega


class CheckoutSerializer(serializers.Serializer):
    items = ItemVentaSerializer(many=True, allow_empty=False)
    entrega = serializers.ChoiceField(choices=Entrega.choices)
    direccion_entrega = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
    )

    def validate(self, datos):
        if datos["entrega"] == Entrega.RETIRO and datos.get("direccion_entrega"):
            raise serializers.ValidationError({
                "direccion_entrega": "El retiro no requiere dirección."
            })

        return datos
