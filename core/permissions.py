from rest_framework.permissions import BasePermission, SAFE_METHODS


class PermisoGuinda(BasePermission):
    """Por ahora: lectura libre, escritura con sesión. Después se agregan los roles acá."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


def es_personal(usuario):
    """True si el usuario es un empleado del local o el superusuario."""
    return bool(
        usuario
        and usuario.is_authenticated
        and (usuario.is_superuser or hasattr(usuario, "empleado"))
    )


class EsCliente(BasePermission):
    """Deja pasar solo a clientes de la tienda web (con sesión y sin ser personal)."""
    message = "Esta sección es para clientes de la tienda."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario
            and usuario.is_authenticated
            and not es_personal(usuario)
            and hasattr(usuario, "cliente")
        )

class EsPersonal(BasePermission):
    """Deja pasar solo a empleados del local y al superusuario."""
    message = "Esta sección es solo para el personal del local."

    def has_permission(self, request, view):
        return es_personal(request.user)


# ============================================================
# Roles y permisos por acción (matriz aprobada por el equipo)
# ============================================================
# Los roles son grupos de Django (los crea la migración seguridad/0002_grupos_roles).
# Cada vista dice qué permiso pide cada acción; la matriz dice qué roles lo tienen.

DUENA = "Dueña"
ENCARGADA = "Encargada"
VENDEDOR = "Vendedor"
RESP_STOCK = "Responsable de stock"
RESP_ONLINE = "Responsable de ventas online"

ADMINISTRACION = {DUENA, ENCARGADA}
TODO_EL_PERSONAL = {DUENA, ENCARGADA, VENDEDOR, RESP_STOCK, RESP_ONLINE}

MATRIZ = {
    # Ventas
    "ver_ventas": ADMINISTRACION | {VENDEDOR, RESP_ONLINE},
    "registrar_venta_presencial": ADMINISTRACION | {VENDEDOR},
    "registrar_venta_online": ADMINISTRACION | {RESP_ONLINE},
    "anular_venta": ADMINISTRACION,
    # Caja
    "ver_caja": ADMINISTRACION | {VENDEDOR, RESP_ONLINE},
    "abrir_caja": ADMINISTRACION | {VENDEDOR},
    "cerrar_caja": ADMINISTRACION,
    "movimiento_manual": ADMINISTRACION,
    "administrar_cajas": ADMINISTRACION,  # alta, edición y baja de cajas y métodos de pago
    # Stock
    "ver_stock": TODO_EL_PERSONAL,
    "mover_stock": ADMINISTRACION | {RESP_STOCK},
    # Pedidos
    "ver_pedidos": TODO_EL_PERSONAL,
    "crear_pedido": ADMINISTRACION | {VENDEDOR, RESP_ONLINE},
    "gestionar_pedido": ADMINISTRACION | {RESP_ONLINE},  # cambiar estado, cancelar, entregar
    # Envíos
    "ver_envios": ADMINISTRACION | {VENDEDOR, RESP_ONLINE},
    "gestionar_envios": ADMINISTRACION | {RESP_ONLINE},
    # Clientes
    "ver_clientes": ADMINISTRACION | {VENDEDOR, RESP_ONLINE},
    "editar_clientes": ADMINISTRACION | {VENDEDOR, RESP_ONLINE},
    "baja_cliente": ADMINISTRACION,
    # Catálogo y promociones
    "gestionar_catalogo": ADMINISTRACION,
    "ver_promociones": TODO_EL_PERSONAL,
    "gestionar_promociones": ADMINISTRACION,
    # Compras y proveedores
    "ver_compras": ADMINISTRACION | {RESP_STOCK},
    "gestionar_compras": ADMINISTRACION,
    "recibir_compra": ADMINISTRACION | {RESP_STOCK},
    "ver_proveedores": ADMINISTRACION | {RESP_STOCK},
    "gestionar_proveedores": ADMINISTRACION,
    # Dashboard y seguridad
    "ver_dashboard": TODO_EL_PERSONAL,
    "gestionar_seguridad": ADMINISTRACION,
    # Auditoria
    "ver_auditoria": {DUENA},

}


def roles_de(usuario):
    """Nombres de los grupos del usuario (se consultan una sola vez por petición)."""
    if not hasattr(usuario, "_roles_guinda"):
        usuario._roles_guinda = set(usuario.groups.values_list("name", flat=True))
    return usuario._roles_guinda


def puede(usuario, permiso):
    """
    True si el usuario tiene el permiso según la matriz.
    El superusuario puede todo; un cliente, nada de esto.
    Si mañana los permisos se administran desde el admin, solo cambia esta función.
    """
    if not es_personal(usuario):
        return False
    if usuario.is_superuser:
        return True
    if permiso not in MATRIZ:
        raise KeyError(f"El permiso «{permiso}» no está en la matriz.")
    return bool(roles_de(usuario) & MATRIZ[permiso])


class PermisoPorAccion(BasePermission):
    """
    La vista declara qué permiso pide cada acción:

        permisos = {"list": "ver_ventas", "anular": "anular_venta", ...}

    Una acción que no figura en el diccionario queda bloqueada (cerrado por defecto).
    En una APIView sin acciones, se declara un solo permiso: permiso = "ver_dashboard".
    """

    def has_permission(self, request, view):
        if not es_personal(request.user):
            self.message = "Esta sección es solo para el personal del local."
            return False

        accion = getattr(view, "action", None)
        if accion == "metadata":  # OPTIONS: el navegador pregunta qué métodos hay
            return True

        if accion is None:
            permiso = getattr(view, "permiso", None)
        else:
            permiso = getattr(view, "permisos", {}).get(accion)

        if permiso is None:
            self.message = "Esta acción no tiene un permiso asignado."
            return False

        if not puede(request.user, permiso):
            self.message = "Su rol no permite realizar esta acción."
            return False
        return True


class LecturaPublicaEscrituraPorRol(BasePermission):
    """
    Para el catálogo: cualquiera consulta (GET), aun sin sesión.
    Para crear, editar, dar de baja o cargar imágenes hace falta el permiso
    que declara la vista: permiso_escritura = "gestionar_catalogo".
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not es_personal(request.user):
            self.message = "Solo el personal del local puede modificar el catálogo."
            return False
        if not puede(request.user, view.permiso_escritura):
            self.message = "Su rol no permite modificar el catálogo."
            return False
        return True