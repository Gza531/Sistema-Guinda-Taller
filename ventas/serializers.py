from rest_framework import serializers

from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Cliente
        fields = [
            "id_cliente", "nombre", "apellido", "tipo_documento", "nro_documento",
            "telefono", "email", "direccion", "fecha_alta", "estado", "usuario",
        ]
        read_only_fields = ["fecha_alta", "usuario"]

    def validate_nro_documento(self, valor):
        # Un documento vacío se guarda como NULL, no como texto vacío
        return valor.strip() or None if valor else None

    def validate(self, datos):
        nombre = datos.get("nombre", getattr(self.instance, "nombre", ""))
        apellido = datos.get("apellido", getattr(self.instance, "apellido", ""))
        if (nombre.strip().lower() == Cliente.CF_NOMBRE.lower()
                and apellido.strip().lower() == Cliente.CF_APELLIDO.lower()):
            raise serializers.ValidationError(
                "«Consumidor Final» es un cliente reservado del sistema; ya existe."
            )
        return datos