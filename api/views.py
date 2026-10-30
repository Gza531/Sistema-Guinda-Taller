from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets
from clientes import services as clientes_services
from django.db.models import Exists, OuterRef, Q
from stock.models import Stock
from decimal import Decimal, InvalidOperation
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.decorators import action
from catalogo import services as catalogo_services
from catalogo.models import (
    ImagenProducto,
    Producto,
    Marca,
    Categoria,
)

from core.mixins import BajaLogicaMixin
from auditoria.models import Auditoria
from auditoria.services import registrar as registrar_auditoria
from core.permissions import LecturaPublicaEscrituraPorRol, es_personal

from django.contrib.auth import authenticate, get_user_model

from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,

)

from catalogo.models import (
    Producto,
    Marca,
    Categoria,
)

from .serializers import (
    ProductoSerializer,
    MarcaSerializer,
    CategoriaSerializer,
    RegistroClienteSerializer,
    ImagenProductoSerializer,
    SubirImagenesSerializer,
    OrdenImagenesSerializer,
)

Usuario = get_user_model()

class EstadoAPIView(APIView):
    """
    Endpoint de ejemplo para confirmar que la API REST esta funcionando.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "estado": "ok",
                "mensaje": "La API REST del proyecto esta funcionando correctamente.",
            },
            status=status.HTTP_200_OK,
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
    ).annotate(
       disponible=Exists(
           Stock.objects.filter(
                producto=OuterRef("pk"),
                cantidad_actual__gt=0
        )
    )
)

    serializer_class = ProductoSerializer

    permission_classes = [LecturaPublicaEscrituraPorRol]
    permiso_escritura = "gestionar_catalogo"
    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Solo el personal puede ver productos inactivos.
        if not es_personal(self.request.user):
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
    
class RegistroAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistroClienteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cliente, vinculado = clientes_services.registrar_cliente(
          **serializer.validated_data
        )

        return Response(
            {
                "mensaje": "Usuario registrado correctamente",
                "id_usuario": cliente.usuario.id_usuario,
                "username": cliente.usuario.username,
                "id_cliente": cliente.id_cliente,
                "vinculado": vinculado,
            },
            status=status.HTTP_201_CREATED
        )

class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        # El username no distingue mayúsculas.
        existente = (
            Usuario.objects.filter(username__iexact=username).first()
            if username else None
        )

        usuario = None

        if existente is not None:
            usuario = authenticate(
                request=request,
                username=existente.username,
                password=password,
            )

        if usuario is None:
            return Response(
                {"mensaje": "Usuario o contraseña incorrectos"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if es_personal(usuario):
            registrar_auditoria(
                usuario=usuario,
                accion=Auditoria.Accion.LOGIN,
                tabla=usuario._meta.db_table,
                id_registro=usuario.pk,
            )

        roles = list(
            usuario.groups.values_list("name", flat=True)
        )

        es_empleado = hasattr(usuario, "empleado")
        refresh = RefreshToken.for_user(usuario)

        if es_personal(usuario):
            registrar_auditoria(
                usuario=usuario,
                accion=Auditoria.Accion.LOGIN,
                tabla=usuario._meta.db_table,
                id_registro=usuario.pk,
            )

        return Response(
            {
                "mensaje": "Login correcto",
                "id_usuario": usuario.id_usuario,
                "username": usuario.username,
                "es_empleado": es_empleado,
                "es_superusuario": usuario.is_superuser,
                "roles": roles,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )

class LogoutAPIView(APIView):
       """
       POST /api/logout/ → registra el cierre de sesión en la auditoría.
       Con JWT, cerrar sesión es borrar los tokens en el navegador: este endpoint
       solo deja constancia. El front lo llama antes de borrarlos.
       """
       permission_classes = [IsAuthenticated]

       def post(self, request):
        if es_personal(request.user):
            registrar_auditoria(
                usuario=request.user,
                accion=Auditoria.Accion.LOGOUT,
                tabla=request.user._meta.db_table,
                id_registro=request.user.pk,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)



class PerfilAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        usuario = request.user

        roles = list(
            usuario.groups.values_list("name", flat=True)
        )

        es_empleado = hasattr(usuario, "empleado")

        return Response(
            {
                "id_usuario": usuario.id_usuario,
                "username": usuario.username,
                "es_empleado": es_empleado,
                "es_superusuario": usuario.is_superuser,
                "roles": roles
            },
            status=status.HTTP_200_OK
        )