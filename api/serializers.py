from rest_framework import serializers
from catalogo.models import Producto, Marca, Categoria, ImagenProducto
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from clientes.models import Cliente
from stock.models import Stock
from promociones.services import descuento_vigente

Usuario = get_user_model()



class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        fields = "__all__"


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = "__all__"

class ImagenProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenProducto
        fields = ["id_imagen_producto", "imagen", "orden", "es_principal"]
        read_only_fields = fields


class ProductoSerializer(serializers.ModelSerializer):
    marca_nombre = serializers.CharField(
        source="marca.nombre",
        read_only=True
    )

    categoria_nombre = serializers.CharField(
        source="categoria.nombre",
        read_only=True
    )

    disponible = serializers.SerializerMethodField()
    precio_promocional = serializers.SerializerMethodField()
    
    # "imagen" es la URL de la foto principal (la usan las tarjetas del catálogo)
    imagen = serializers.SerializerMethodField()
    imagenes = ImagenProductoSerializer(many=True, read_only=True)

    def get_disponible(self, obj):
        if hasattr(obj, "disponible"):
            return obj.disponible

        return Stock.objects.filter(
            producto=obj,
            cantidad_actual__gt=0
        ).exists()

    def get_imagen(self, obj):
        imagenes = list(obj.imagenes.all())
        if not imagenes:
            return None

        # Si por algún motivo ninguna está marcada, se usa la primera
        principal = next((i for i in imagenes if i.es_principal), imagenes[0])

        request = self.context.get("request")
        url = principal.imagen.url
        return request.build_absolute_uri(url) if request else url

    def get_precio_promocional(self, obj):
        promocion, monto = descuento_vigente(obj)

        if promocion is None:
            return None

        return str(obj.precio_venta - monto)

    class Meta:
        model = Producto
        fields = "__all__"

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



class SubirImagenesSerializer(serializers.Serializer):
    imagenes = serializers.ListField(
        child=serializers.ImageField(),
        allow_empty=False
    )


class OrdenImagenesSerializer(serializers.Serializer):
    orden = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )