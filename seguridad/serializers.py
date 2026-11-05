from rest_framework import serializers

from core.permissions import TODO_EL_PERSONAL

from .models import Empleado

# Tomamos el conjunto de todo el personal y los devolvemos en una lista ordenada

ROLES_PERSONAL = sorted(TODO_EL_PERSONAL)


# Toma el nombre ede cada grupo de la cuenta y devuelve los roles ordenados.
# Si el empleado no tiene una cuenta asociada entonces devuelve una lista vacía

class EmpleadoSerializer(serializers.ModelSerializer):
    """Salida: lo que devuelve la API (nunca la contraseña)."""

    username = serializers.CharField(source="usuario.username", read_only=True, default=None)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = Empleado
        fields = [
            "id_empleado", "nombre", "apellido", "dni", "telefono", "email",
            "fecha_alta", "estado", "usuario", "username", "roles",
        ]
        read_only_fields = fields

    def get_roles(self, empleado):
        if not empleado.usuario:
            return []
        return sorted(g.name for g in empleado.usuario.groups.all())

# "limpiamos" el DNI, teléfono y Email antes de guardarlos. Si un campo viene vacío se convierte en null

class _DatosPersonalesMixin:
    """Un DNI, teléfono o email vacío se guarda como NULL (son únicos en la base)."""

    def _vacio_a_null(self, valor):
        valor = (valor or "").strip()
        return valor or None

    def validate_dni(self, valor):
        return self._vacio_a_null(valor)

    def validate_telefono(self, valor):
        return self._vacio_a_null(valor)

    def validate_email(self, valor):
        return self._vacio_a_null(valor)


# Valida datos para dar de alta a un empleado 
# Deja los datos listos para que el servicio cree la cuenta y la ficha del empleado

class NuevoEmpleadoSerializer(_DatosPersonalesMixin, serializers.ModelSerializer):
    """Entrada del alta: datos personales + usuario + contraseña + roles."""

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=ROLES_PERSONAL), allow_empty=False
    )

    class Meta:
        model = Empleado
        fields = ["nombre", "apellido", "dni", "telefono", "email", "username", "password", "roles"]
        extra_kwargs = {
            "dni": {"required": False, "allow_null": True, "allow_blank": True},
            "telefono": {"required": False, "allow_null": True, "allow_blank": True},
            "email": {"required": False, "allow_null": True, "allow_blank": True},
        }

# Valida los datos enviados para editar un empleado por PATCH
# Permite enviar sólo los campos que se quieren cambiar

class EditarEmpleadoSerializer(_DatosPersonalesMixin, serializers.ModelSerializer):
    """Entrada del PATCH: todo opcional. estado = true reactiva."""

    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=ROLES_PERSONAL), allow_empty=False, required=False
    )

    class Meta:
        model = Empleado
        fields = ["nombre", "apellido", "dni", "telefono", "email", "estado", "roles"]
        extra_kwargs = {
            "dni": {"allow_null": True, "allow_blank": True},
            "telefono": {"allow_null": True, "allow_blank": True},
            "email": {"allow_null": True, "allow_blank": True},
        }

# Valida el campo password para el cambio de contraseña, sin incluirlo en la respuesta
# Recibe la contraseña nueva sin quitar espacios y se acepta como entrada.

class CambiarPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)