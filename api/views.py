from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from auditoria.models import Auditoria
from auditoria.services import registrar as registrar_auditoria
from clientes import services as clientes_services
from core.permissions import es_personal, permisos_de

from .serializers import RegistroClienteSerializer

# Autenticación y cuenta: login, logout, registro de clientes y perfil.
# El catálogo (productos, marcas y categorías) está en la app catalogo.

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
                "roles": roles,
                "permisos" : permisos_de(usuario),
                "empleado": (
                    {
                        "nombre": usuario.empleado.nombre,
                        "apellido": usuario.empleado.apellido,
                        "dni": usuario.empleado.dni,
                        "email": usuario.empleado.email,
                        "telefono": usuario.empleado.telefono,
                        "fecha_alta": usuario.empleado.fecha_alta,
                    }
                    if es_empleado else None
                ),
            },
            status=status.HTTP_200_OK
        )