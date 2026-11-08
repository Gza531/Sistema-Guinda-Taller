
import re
import unicodedata

from rest_framework import serializers


def validar_nombre_persona(valor, campo):
    texto = " ".join(unicodedata.normalize("NFC", valor).split())

    if not texto:
        raise serializers.ValidationError(f"Ingrese su {campo}.")

    partes = re.split(r"[ '\u2019-]", texto)

    if not all(parte.isalpha() for parte in partes):
        raise serializers.ValidationError(
            f"El {campo} solo puede contener letras."
        )

    return texto
