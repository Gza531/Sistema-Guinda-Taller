from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from clientes.models import Cliente
from clientes.validaciones import validar_nombre_persona

Usuario = get_user_model()



class RegistroClienteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    nombre = serializers.CharField(max_length=60)
    apellido = serializers.CharField(max_length=60)

    email = serializers.EmailField()
    telefono = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True
    )
    direccion = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True
    )
    tipo_documento = serializers.ChoiceField(
        choices=Cliente.TipoDocumento.choices,
        required=False,
        allow_null=True
    )
    nro_documento = serializers.CharField(
        max_length=13,
        required=False,
        allow_blank=True,
        allow_null=True
    )

    def validate_nombre(self, valor):
        return validar_nombre_persona(valor, "nombre")

    def validate_apellido(self, valor):
        return validar_nombre_persona(valor, "apellido")

    def validate_username(self, value):
        if Usuario.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "Ya existe un usuario con ese nombre."
            )
        return value

    def validate_email(self, value):
        value = (value or "").strip().lower()

        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta con ese email."
            )

        return value


    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_nro_documento(self, value):
      return value.strip() if value else None

    def validate(self, datos):
        nombre = datos.get("nombre", "")
        apellido = datos.get("apellido", "")

        if (
            nombre.strip().lower() == Cliente.CF_NOMBRE.lower()
            and apellido.strip().lower() == Cliente.CF_APELLIDO.lower()
        ):
            raise serializers.ValidationError(
                "«Consumidor Final» es un cliente reservado del sistema."
            )

        tipo = datos.get("tipo_documento")
        nro = datos.get("nro_documento")

        if bool(tipo) != bool(nro):
            raise serializers.ValidationError({
                "nro_documento": "El tipo y el número de documento van juntos: completá los dos o ninguno."
            })
        return datos
