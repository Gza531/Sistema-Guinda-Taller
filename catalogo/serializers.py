from rest_framework import serializers

from pedidos.reservas import reservadas
from promociones.services import descuento_vigente
from stock.models import Stock

from .models import Categoria, ImagenProducto, Marca, Producto


# Límite comercial: unidades de un mismo producto por compra en la tienda web.
# La API nunca manda más que esto, así el cliente no ve cuánto stock hay
# cuando sobra: solo sabe hasta cuántas unidades puede llevar.
MAXIMO_POR_COMPRA = 30


class NombreUnicoMixin:
    """
    El nombre no puede repetirse aunque cambien mayúsculas o espacios:
    «Dior», «dior» y « DIOR » son la misma marca.
    """
    etiqueta = "un registro"  # cada serializer dice "una marca", "una categoría"...

    def validate_nombre(self, valor):
        nombre = " ".join(valor.split())  # saca espacios de más, también en el medio
        modelo = self.Meta.model
        repetido = modelo.objects.filter(nombre__iexact=nombre)
        if self.instance is not None:
            repetido = repetido.exclude(pk=self.instance.pk)
        existente = repetido.first()
        if existente:
            raise serializers.ValidationError(
                f"Ya existe {self.etiqueta} llamada «{existente.nombre}»."
            )
        return nombre


class MarcaSerializer(NombreUnicoMixin, serializers.ModelSerializer):
    etiqueta = "una marca"

    class Meta:
        model = Marca
        fields = "__all__"
        # La unicidad la controla validate_nombre (sin distinguir mayúsculas)
        extra_kwargs = {"nombre": {"validators": []}}


class CategoriaSerializer(NombreUnicoMixin, serializers.ModelSerializer):
    etiqueta = "una categoría"

    class Meta:
        model = Categoria
        fields = "__all__"
        extra_kwargs = {"nombre": {"validators": []}}

class ImagenProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenProducto
        fields = ["id_imagen_producto", "imagen", "orden", "es_principal"]
        read_only_fields = fields


class ProductoSerializer(serializers.ModelSerializer):
    stock_sucursal = serializers.IntegerField(read_only=True)
    stock_deposito = serializers.IntegerField(read_only=True)
    # Unidades del Depósito apartadas para pedidos abiertos (solo para el personal)
    stock_reservado = serializers.SerializerMethodField()

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

    # Hasta cuántas unidades puede poner el cliente en la bolsa: el stock del
    # Depósito (de ahí salen las ventas online), como mucho MAXIMO_POR_COMPRA.
    maximo_compra = serializers.SerializerMethodField()

    # True si el máximo es el límite comercial (puede haber más stock):
    # la tienda muestra "Alcanzaste el máximo permitido por compra" en vez de
    # "No hay más unidades disponibles".
    maximo_es_limite = serializers.SerializerMethodField()
    
    # "imagen" es la URL de la foto principal (la usan las tarjetas del catálogo)
    imagen = serializers.SerializerMethodField()
    imagenes = ImagenProductoSerializer(many=True, read_only=True)

    def get_stock_reservado(self, obj):
        # Solo lo trae anotado la lista del personal (ProductoViewSet)
        if getattr(obj, "stock_deposito", None) is None:
            return None
        return getattr(obj, "stock_reservado", 0)

    def get_disponible(self, obj):
        if hasattr(obj, "disponible"):
            return obj.disponible

        # Igual que en ProductoViewSet: disponible para la tienda = hay en el Depósito
        # sin contar lo apartado para pedidos
        return self._stock_tienda(obj) > 0

    def _stock_tienda(self, obj):
        stock = getattr(obj, "stock_para_tienda", None)

        # Sin la anotación de ProductoViewSet (ej. Mis favoritos): se consulta
        # una vez y se guarda en el objeto para los campos que lo usan
        if stock is None:
            stock = (
                Stock.objects
                .filter(producto=obj, ubicacion=Stock.Ubicaciones.DEPOSITO)
                .values_list("cantidad_actual", flat=True)
                .first()
            ) or 0
            stock -= reservadas(obj)
            obj.stock_para_tienda = stock

        return max(0, stock)

    def get_maximo_compra(self, obj):
        return min(self._stock_tienda(obj), MAXIMO_POR_COMPRA)

    def get_maximo_es_limite(self, obj):
        return self._stock_tienda(obj) >= MAXIMO_POR_COMPRA

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
