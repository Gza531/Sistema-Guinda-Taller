from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets

from django.contrib.auth import authenticate

from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework.permissions import (
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


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.select_related(
        "marca",
        "categoria"
    ).all()

    serializer_class = ProductoSerializer

    permission_classes = [
        IsAuthenticatedOrReadOnly
    ]


class MarcaViewSet(viewsets.ModelViewSet):
    queryset = Marca.objects.all()

    serializer_class = MarcaSerializer

    permission_classes = [
        IsAuthenticatedOrReadOnly
    ]


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()

    serializer_class = CategoriaSerializer

    permission_classes = [
        IsAuthenticatedOrReadOnly
    ]


class LoginAPIView(APIView):

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