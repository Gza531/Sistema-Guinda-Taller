from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import PermisoPorAccion

from . import services
from .models import Empleado
from .serializers import (
    ROLES_PERSONAL,
    CambiarPasswordSerializer,
    EditarEmpleadoSerializer,
    EmpleadoSerializer,
    NuevoEmpleadoSerializer,
)


# Atiende las consultas y los cambios de empleados desde la API.
# Comprueba permisos, usa los serializers y delega los cambios a los servicios.

class EmpleadoViewSet(viewsets.ModelViewSet):
    """
    /api/seguridad/empleados/
      GET     lista (filtros: ?buscar=texto, ?estado=true|false)
      POST    alta (crea el usuario, el empleado y le asigna los roles)
      PATCH   /{id}/ datos, roles o reactivación ({"estado": true})
      DELETE  /{id}/ baja lógica (además bloquea el inicio de sesión)
      POST    /{id}/cambiar-password/  {"password": "..."}
    """

    serializer_class = EmpleadoSerializer
    permission_classes = [PermisoPorAccion]
    
    # Permiso que viene de core

    permisos = {
        "list": "gestionar_seguridad",
        "retrieve": "gestionar_seguridad",
        "create": "gestionar_seguridad",
        "partial_update": "gestionar_seguridad",
        "destroy": "gestionar_seguridad",
        "cambiar_password": "gestionar_seguridad",
    }
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    # Definimos que empleados consulta la vista

    def get_queryset(self):

        #Traemos un empleado y su rol 

        qs = (
            Empleado.objects
            .select_related("usuario")
            .prefetch_related("usuario__groups")
            .order_by("apellido", "nombre")
        )

        #Filtramos el listado de empleados por estado

        estado = self.request.query_params.get("estado")
        if estado in ("true", "1"):
            qs = qs.filter(estado=True)
        elif estado in ("false", "0"):
            qs = qs.filter(estado=False)


        #Busca por texto al listado del empleado
        # Alcanza con que el texto aparezca en uno de los campos, sin distinguir mayúsculas.
        # Si se pidió un filtro por estado, se mantiene.
        
        buscar = self.request.query_params.get("buscar")
        if buscar:
            qs = qs.filter(
                Q(nombre__icontains=buscar)
                | Q(apellido__icontains=buscar)
                | Q(dni__icontains=buscar)
                | Q(usuario__username__icontains=buscar)
            )
        return qs


    # Elige la clase de serializer según la acción; por defecto devuelve EmpleadoSerializer.

    def get_serializer_class(self):
        if self.action == "create":
            return NuevoEmpleadoSerializer
        if self.action == "partial_update":
            return EditarEmpleadoSerializer
        if self.action == "cambiar_password":
            return CambiarPasswordSerializer
        return EmpleadoSerializer

    # Método auxiliar, arma la respuesta que recibe el front
    # Vuelve a consultar la ficha del empleado y devuelve sus datos con el código HTTP indicado.

    def _respuesta(self, empleado, codigo=status.HTTP_200_OK):
        empleado = self.get_queryset().get(pk=empleado.pk)
        return Response(EmpleadoSerializer(empleado).data, status=codigo)


    # Valida los datos del alta, llama al servicio para crear al empleado
    # y devuelve la ficha creada con el código HTTP 201.

    def create(self, request):
        entrada = NuevoEmpleadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        empleado = services.crear_empleado(actor=request.user, **entrada.validated_data)
        return self._respuesta(empleado, status.HTTP_201_CREATED)

    # Valida los cambios del PATCH y pasa una copia de los datos al servicio para aplicarlos.
    # Devuelve la ficha actualizada con HTTP 200.

    def partial_update(self, request, pk=None):
        empleado = self.get_object()
        entrada = EditarEmpleadoSerializer(empleado, data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        empleado = services.actualizar_empleado(
            actor=request.user, empleado=empleado, datos=dict(entrada.validated_data)
        )
        return self._respuesta(empleado)


    # Busca al empleado, aplica la baja lógica mediante el servicio y devuelve la ficha con su nuevo estado.

    def destroy(self, request, pk=None):
        empleado = services.dar_de_baja(actor=request.user, empleado=self.get_object())
        return self._respuesta(empleado)

# Valida la contraseña nueva, delega el cambio al servicio y confirma el resultado.

    @action(detail=True, methods=["post"], url_path="cambiar-password")
    def cambiar_password(self, request, pk=None):
        entrada = CambiarPasswordSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        services.cambiar_password(
            actor=request.user, empleado=self.get_object(),
            password=entrada.validated_data["password"],
        )
        return Response({"mensaje": "Contraseña actualizada."})


# Devuelve la lista de roles del personal para el formulario de empleados.

class RolesAPIView(APIView):
    """GET /api/seguridad/roles/ → los roles del personal, para el formulario."""

    permission_classes = [PermisoPorAccion]
    permiso = "gestionar_seguridad"

    def get(self, request):
        return Response(ROLES_PERSONAL)