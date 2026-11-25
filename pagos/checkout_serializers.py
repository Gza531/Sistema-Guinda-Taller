import re

from rest_framework import serializers

from ventas.serializers import ItemVentaSerializer
from ventas.services import Entrega

from .tarifas import PROVINCIAS, numero_postal


class CheckoutSerializer(serializers.Serializer):
    items = ItemVentaSerializer(many=True, allow_empty=False)
    entrega = serializers.ChoiceField(choices=Entrega.choices)
    direccion_entrega = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
    )

    # Destino del envío: con la provincia y el código postal se calcula el costo
    # por zona (pagos/tarifas.py). Con retiro en el local no se usan.
    provincia = serializers.ChoiceField(
        choices=PROVINCIAS,
        required=False,
        allow_blank=True,
    )
    codigo_postal = serializers.CharField(
        max_length=8,
        required=False,
        allow_blank=True,
    )

    # Datos de contacto para el envío a domicilio (si faltan, se usan los de
    # Mi perfil). Con retiro en el local no se usan.
    telefono = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )
    nro_documento = serializers.CharField(
        max_length=13,
        required=False,
        allow_blank=True,
    )

    def validate_codigo_postal(self, valor):
        valor = valor.strip().upper()
        if valor and not numero_postal(valor):
            raise serializers.ValidationError(
                "Usá 4 números (ej. 4400) o el formato A4400ABC."
            )
        return valor

    def validate_telefono(self, valor):
        valor = " ".join(valor.split())
        if not valor:
            return ""

        digitos = re.sub(r"\D", "", valor)
        if not re.fullmatch(r"\+?[\d\s()-]+", valor) or not 8 <= len(digitos) <= 15:
            raise serializers.ValidationError(
                "Ingresá un teléfono válido, con código de área (ej. 387 5551234)."
            )
        return valor

    def validate_nro_documento(self, valor):
        # Se aceptan puntos o espacios (38.124.567) y se guarda solo el número
        valor = re.sub(r"[.\s-]", "", valor)
        if valor and not valor.isdigit():
            raise serializers.ValidationError("El documento lleva solo números.")
        return valor

    def validate(self, datos):
        if datos["entrega"] == Entrega.RETIRO and datos.get("direccion_entrega"):
            raise serializers.ValidationError({
                "direccion_entrega": "El retiro no requiere dirección."
            })

        return datos
