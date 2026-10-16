from rest_framework import serializers
from catalogo.models import Producto, Marca, Categoria
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from clientes.models import Cliente

Usuario = get_user_model()


class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        fields = "__all__"


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = "__all__"


class ProductoSerializer(serializers.ModelSerializer):
    marca_nombre = serializers.CharField(
        source="marca.nombre",
        read_only=True
    )

    categoria_nombre = serializers.CharField(
        source="categoria.nombre",
        read_only=True
    )

    class Meta:
        model = Producto
        fields = "__all__"

class RegistroClienteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    nombre = serializers.CharField(max_length=60)
    apellido = serializers.CharField(max_length=60)

    email = serializers.EmailField(required=False, allow_blank=True)
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

    def validate_username(self, value):
        if Usuario.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "Ya existe un usuario con ese nombre."
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_nro_documento(self, value):
        value = value.strip() if value else None

        if value and Cliente.objects.filter(nro_documento=value).exists():
            raise serializers.ValidationError(
                "Ya existe un cliente con ese número de documento."
            )

        return value

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

        return datos