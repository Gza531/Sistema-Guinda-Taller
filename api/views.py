from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets
from django.db.models import Exists, OuterRef, Q
from stock.models import Stock
from decimal import Decimal, InvalidOperation
from rest_framework.exceptions import ValidationError

from core.mixins import BajaLogicaMixin

from django.contrib.auth import authenticate

from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
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
)


class EstadoAPIView(APIView):
    """
    Endpoint de ejemplo para confirmar que la API REST esta funcionando.
    """

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
        return Decimal(valor)
    except InvalidOperation:
        raise ValidationError({
            campo: "Debe ser un número, por ejemplo 15000 o 15000.50."
        })

class ProductoViewSet(BajaLogicaMixin, viewsets.ModelViewSet):
    queryset = Producto.objects.select_related(
        "marca",
        "categoria"
    ).annotate(
       disponible=Exists(
           Stock.objects.filter(
                producto=OuterRef("pk"),
                cantidad_actual__gt=0
        )
    )
)

    serializer_class = ProductoSerializer

    permission_classes = [
        IsAuthenticatedOrReadOnly
    ]
    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # El catálogo es público: quien no inició sesión solo ve productos activos.
        if not self.request.user.is_authenticated:
            qs = qs.filter(estado=True)

        marca = params.get("marca")
        categoria = params.get("categoria")
        precio_min = params.get("precio_min")
        precio_max = params.get("precio_max")
        search = params.get("search")
        disponible = params.get("disponible")

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


class MarcaViewSet(BajaLogicaMixin, viewsets.ModelViewSet):
    queryset = Marca.objects.all()

    serializer_class = MarcaSerializer

    permission_classes = [
        IsAuthenticatedOrReadOnly
    ]


class CategoriaViewSet(BajaLogicaMixin, viewsets.ModelViewSet):
    queryset = Categoria.objects.all()

    serializer_class = CategoriaSerializer

    permission_classes = [
        IsAuthenticatedOrReadOnly
    ]


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        usuario = authenticate(
            request=request,
            username=username,
            password=password
        )

        if usuario is not None:

            roles = list(
                usuario.groups.values_list("name", flat=True)
            )

            es_empleado = hasattr(usuario, "empleado")

            refresh = RefreshToken.for_user(usuario)

            return Response(
                {
                    "mensaje": "Login correcto",
                    "id_usuario": usuario.id_usuario,
                    "username": usuario.username,
                    "es_empleado": es_empleado,
                    "es_superusuario": usuario.is_superuser,
                    "roles": roles,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token)
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "mensaje": "Usuario o contraseña incorrectos"
            },
            status=status.HTTP_401_UNAUTHORIZED
        )


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