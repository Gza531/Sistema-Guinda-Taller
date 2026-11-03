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

        # ← nuevo: tipo y número de documento van juntos
        tipo = datos.get("tipo_documento", getattr(self.instance, "tipo_documento", None))
        nro = datos.get("nro_documento", getattr(self.instance, "nro_documento", None))
        if bool(tipo) != bool(nro):
            raise serializers.ValidationError(
                {"nro_documento": "El tipo y el número de documento van juntos: completá los dos o ninguno."}
            )
        return datos


# ---------- Mi perfil ----------

class MiPerfilSerializer(serializers.ModelSerializer):
    """Salida: lo que el cliente ve de sí mismo (sin datos internos como «estado» o ids)."""
    username = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = Cliente
        fields = [
            "username", "nombre", "apellido", "email", "telefono", "direccion",
            "tipo_documento", "nro_documento", "fecha_alta",
        ]
        read_only_fields = fields


def _limpiar(valor):
    """' Mitre  123 ' -> 'Mitre 123'; vacío -> None."""
    if not valor:
        return None
    return " ".join(valor.split()) or None


class EditarMiPerfilSerializer(serializers.Serializer):
    """Entrada del PATCH: todos los campos son opcionales, se cambia solo lo que llega."""
    nombre = serializers.CharField(max_length=60, required=False)
    apellido = serializers.CharField(max_length=60, required=False)
    email = serializers.EmailField(max_length=100, required=False)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    direccion = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    tipo_documento = serializers.ChoiceField(
        choices=Cliente.TipoDocumento.choices, required=False, allow_null=True, allow_blank=True
    )
    nro_documento = serializers.CharField(max_length=13, required=False, allow_blank=True, allow_null=True)

    def validate_nombre(self, valor):
        return " ".join(valor.split())

    def validate_apellido(self, valor):
        return " ".join(valor.split())

    def validate_email(self, valor):
        return valor.strip().lower()

    def validate_telefono(self, valor):
        return _limpiar(valor)

    def validate_direccion(self, valor):
        return _limpiar(valor)

    def validate_tipo_documento(self, valor):
        return valor or None

    def validate_nro_documento(self, valor):
        return _limpiar(valor)

    def validate(self, datos):
        if not datos:
            raise serializers.ValidationError("No llegó ningún dato para modificar.")

        nombre = datos.get("nombre", getattr(self.instance, "nombre", ""))
        apellido = datos.get("apellido", getattr(self.instance, "apellido", ""))
        if (nombre.lower() == Cliente.CF_NOMBRE.lower()
                and apellido.lower() == Cliente.CF_APELLIDO.lower()):
            raise serializers.ValidationError(
                "«Consumidor Final» es un cliente reservado del sistema."
            )
        return datos


class CambiarMiPasswordSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True)
    password_nueva = serializers.CharField(write_only=True)
    password_repetida = serializers.CharField(write_only=True)

    def validate(self, datos):
        if datos["password_nueva"] != datos["password_repetida"]:
            raise serializers.ValidationError({"password_repetida": "Las contraseñas no coinciden."})
        return datos