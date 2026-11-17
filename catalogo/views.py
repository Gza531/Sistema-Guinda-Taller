from decimal import Decimal, InvalidOperation

from django.db.models import (
    BooleanField, ExpressionWrapper, F, IntegerField, OuterRef, Q, Subquery, Value,
)
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from core.mixins import BajaLogicaMixin
from core.permissions import LecturaPublicaEscrituraPorRol, es_personal
from pedidos.reservas import subconsulta_reservadas
from stock.models import Stock

from . import services as catalogo_services
from .models import Categoria, ImagenProducto, Marca, Producto
from .serializers import (
    CategoriaSerializer,
    ImagenProductoSerializer,
    MarcaSerializer,
    OrdenImagenesSerializer,
    ProductoSerializer,
    SubirImagenesSerializer,
)


def _entero(valor, campo):
    try:
        return int(valor)
    except ValueError:
        raise ValidationError({campo: "Debe ser un número entero."})


def _decimal(valor, campo):
    try:
        numero = Decimal(valor)
    except InvalidOperation:
        numero = None

    if numero is None or not numero.is_finite():
        raise ValidationError({
            campo: "Debe ser un número, por ejemplo 15000 o 15000.50."
        })

    return numero

class ProductoViewSet(BajaLogicaMixin, viewsets.ModelViewSet):
    queryset = Producto.objects.select_related(
        "marca",
        "categoria"
    ).prefetch_related(
        "imagenes"
    )

    serializer_class = ProductoSerializer

    permission_classes = [LecturaPublicaEscrituraPorRol]
    permiso_escritura = "gestionar_catalogo"
    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        deposito = Stock.objects.filter(
            producto_id=OuterRef("pk"),
            ubicacion=Stock.Ubicaciones.DEPOSITO,
        ).values("cantidad_actual")[:1]

        # Lo que puede vender la tienda: el Depósito menos las unidades apartadas
        # para pedidos (pedidos/reservas.py). Lo que hay en la Sucursal (salón) no cuenta:
        # es para la venta presencial.
        # stock_para_tienda es para el tope de la bolsa (ProductoSerializer.maximo_compra);
        # no es un campo del serializer: el número exacto no sale en la respuesta.
        qs = qs.annotate(
            stock_reservado=subconsulta_reservadas(),
            stock_para_tienda=Coalesce(
                Subquery(deposito),
                Value(0),
                output_field=IntegerField(),
            ) - F("stock_reservado"),
        ).annotate(
            # "disponible" = se puede comprar en la tienda online
            disponible=ExpressionWrapper(Q(stock_para_tienda__gt=0), output_field=BooleanField()),
        )

        # El personal puede consultar el stock por ubicación.
        if es_personal(self.request.user):
            sucursal = Stock.objects.filter(
                producto_id=OuterRef("pk"),
                ubicacion=Stock.Ubicaciones.SUCURSAL,
            ).values("cantidad_actual")[:1]

            qs = qs.annotate(
                stock_sucursal=Coalesce(
                    Subquery(sucursal),
                    Value(0),
                    output_field=IntegerField(),
                ),
                stock_deposito=Coalesce(
                    Subquery(deposito),
                    Value(0),
                    output_field=IntegerField(),
                ),
            )
        else:
            # La tienda pública solo muestra productos activos.
            qs = qs.filter(estado=True)

        marca = params.get("marca")
        categoria = params.get("categoria")
        precio_min = params.get("precio_min")
        precio_max = params.get("precio_max")
        search = params.get("search")
        disponible = params.get("disponible")

        if precio_min and precio_max:
            minimo = _decimal(precio_min, "precio_min")
            maximo = _decimal(precio_max, "precio_max")

            if minimo > maximo:
                raise ValidationError({
                    "precio": "El precio mínimo no puede ser mayor que el precio máximo."
                })

        if marca:
            qs = qs.filter(marca_id=_entero(marca, "marca"))

        if categoria:
            qs = qs.filter(categoria_id=_entero(categoria, "categoria"))

        if precio_min:
            qs = qs.filter(
                precio_venta__gte=_decimal(precio_min, "precio_min")
            )

        if precio_max:
            qs = qs.filter(
                precio_venta__lte=_decimal(precio_max, "precio_max")
            )

        if search:
            qs = qs.filter(
                Q(nombre__icontains=search)
                | Q(descripcion__icontains=search)
                | Q(marca__nombre__icontains=search)
                | Q(categoria__nombre__icontains=search)
            )

        if disponible in ("true", "1"):
            qs = qs.filter(disponible=True)
        elif disponible in ("false", "0"):
            qs = qs.filter(disponible=False)

        return qs.order_by("nombre")
    
    # ---------- Fotos del producto ----------

    def _imagenes(self, producto):
        # Se consulta de nuevo: producto.imagenes.all() traería la lista vieja
        # que quedó en memoria por el prefetch_related del queryset.
        imagenes = ImagenProducto.objects.filter(producto=producto)
        return Response(ImagenProductoSerializer(
            imagenes, many=True, context={"request": self.request}
        ).data)

    def _imagen_del_producto(self, producto, id_imagen):
        imagen = ImagenProducto.objects.filter(pk=id_imagen, producto=producto).first()
        if imagen is None:
            raise NotFound("Esa foto no existe o no es de este producto.")
        return imagen

    @action(detail=True, methods=["post"])
    def imagenes(self, request, pk=None):
        """Sube una o varias fotos (multipart, campo «imagenes»)."""
        producto = self.get_object()
        entrada = SubirImagenesSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        catalogo_services.agregar_imagenes(
            producto=producto,
            archivos=entrada.validated_data["imagenes"],
        )
        return self._imagenes(producto)

    @action(detail=True, methods=["post"], url_path="imagenes/orden")
    def ordenar_imagenes(self, request, pk=None):
        """Recibe {"orden": [id, id, ...]} con todas las fotos en el orden nuevo."""
        producto = self.get_object()
        entrada = OrdenImagenesSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        catalogo_services.ordenar_imagenes(
            producto=producto,
            ids=entrada.validated_data["orden"],
        )
        return self._imagenes(producto)

    @action(detail=True, methods=["post"], url_path=r"imagenes/(?P<id_imagen>\d+)/principal")
    def imagen_principal(self, request, pk=None, id_imagen=None):
        producto = self.get_object()
        imagen = self._imagen_del_producto(producto, id_imagen)

        catalogo_services.marcar_principal(imagen=imagen)
        return self._imagenes(producto)

    @action(detail=True, methods=["delete"], url_path=r"imagenes/(?P<id_imagen>\d+)")
    def eliminar_imagen(self, request, pk=None, id_imagen=None):
        producto = self.get_object()
        imagen = self._imagen_del_producto(producto, id_imagen)

        catalogo_services.eliminar_imagen(imagen=imagen)
        return self._imagenes(producto)


class SoloActivasParaPublicoMixin:
    """
    El público (visitantes y clientes) solo ve los registros activos;
    el personal ve todos, para poder reactivarlos.
    """

    def get_queryset(self):
        qs = super().get_queryset()  # ya trae el filtro ?estado= del BajaLogicaMixin
        if not es_personal(self.request.user):
            qs = qs.filter(estado=True)
        return qs


class MarcaViewSet(SoloActivasParaPublicoMixin, BajaLogicaMixin, viewsets.ModelViewSet):
    queryset = Marca.objects.order_by("nombre")
    serializer_class = MarcaSerializer

    permission_classes = [LecturaPublicaEscrituraPorRol]
    permiso_escritura = "gestionar_catalogo"


class CategoriaViewSet(SoloActivasParaPublicoMixin, BajaLogicaMixin, viewsets.ModelViewSet):
    queryset = Categoria.objects.order_by("nombre")
    serializer_class = CategoriaSerializer

    permission_classes = [LecturaPublicaEscrituraPorRol]
    permiso_escritura = "gestionar_catalogo"
