from decimal import Decimal
import logging

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogo.serializers import MAXIMO_POR_COMPRA
from clientes import services as clientes_services
from clientes.models import Cliente
from ventas.services import (
    DEPOSITO,
    Entrega,
    _agrupar,
    _armar_lineas,
    _verificar_stock,
)

from .checkout_serializers import CheckoutSerializer
from .services import ErrorMercadoPago, crear_preferencia
from .tarifas import tarifa_envio
from seguridad.models import Empleado

logger = logging.getLogger(__name__)

# Cantidad de números según el tipo de documento del cliente
LARGO_DOCUMENTO = {
    Cliente.TipoDocumento.DNI: (7, 8),
    Cliente.TipoDocumento.CUIT: (11, 11),
    Cliente.TipoDocumento.CUIL: (11, 11),
}


def _datos_de_contacto(*, cliente, datos):
    """
    Teléfono y documento para el envío a domicilio: los que mandó el cliente o,
    si no mandó, los de su perfil. Son obligatorios para que el correo pueda
    avisarle y entregarle. Devuelve los cambios a guardar en su perfil.

    El documento solo se puede cambiar hasta la primera compra (misma regla que
    Mi perfil): si ya compró, tiene que llegar el mismo que tiene cargado.
    """
    errores = {}

    telefono = datos.get("telefono") or cliente.telefono or ""
    if not telefono:
        errores["telefono"] = "Indicá un teléfono de contacto para el envío."

    tipo = cliente.tipo_documento or Cliente.TipoDocumento.DNI
    nro = datos.get("nro_documento") or cliente.nro_documento or ""
    minimo, maximo = LARGO_DOCUMENTO.get(tipo, (7, 11))

    if not nro:
        errores["nro_documento"] = f"Indicá tu {tipo} para el envío."
    elif not minimo <= len(nro) <= maximo:
        cifras = f"{minimo} u {maximo}" if minimo != maximo else str(minimo)
        errores["nro_documento"] = f"El {tipo} tiene {cifras} números."

    if errores:
        raise ValidationError(errores)

    cambios = {}
    if telefono != cliente.telefono:
        cambios["telefono"] = telefono
    if nro != cliente.nro_documento:
        cambios.update(tipo_documento=tipo, nro_documento=nro)
    return cambios


def _costo_de_envio(datos):
    """Costo del envío según la zona (provincia y código postal del destino)."""
    errores = {}
    if not datos.get("provincia"):
        errores["provincia"] = "Elegí la provincia de entrega."
    if not datos.get("codigo_postal"):
        errores["codigo_postal"] = "Ingresá el código postal de entrega."
    if errores:
        raise ValidationError(errores)

    return tarifa_envio(datos["provincia"], datos["codigo_postal"])["costo"]


class PagoNoDisponible(APIException):
    status_code = 503
    default_detail = "No se pudo iniciar el pago. Intentá nuevamente."
    default_code = "pago_no_disponible"


class CheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Primero verificamos los permisos del usuario.

        if (
            request.user.is_staff
            or request.user.is_superuser
            or Empleado.objects.filter(usuario=request.user).exists()
        ):
            raise PermissionDenied(
                "El personal no puede realizar compras desde este checkout."
            )

        # Después validamos los datos del carrito.
        entrada = CheckoutSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        # El cliente sale del usuario autenticado.
        cliente = Cliente.objects.filter(
            usuario=request.user,
            estado=True,
        ).first()

        if cliente is None or cliente.es_consumidor_final:
            raise PermissionDenied(
                "Necesitás un cliente activo asociado a tu usuario."
            )

        # Reutilizamos las reglas de Ventas.
        cantidades = _agrupar(datos["items"])

        # Límite comercial de la tienda: hasta MAXIMO_POR_COMPRA unidades de cada
        # producto (sumando si viene repetido). Se revisa antes que el stock para
        # que el mensaje no revele cuántas unidades hay cuando sobran.
        excedidos = [
            producto.nombre
            for producto, cantidad in cantidades.items()
            if cantidad > MAXIMO_POR_COMPRA
        ]
        if excedidos:
            # En lista, igual que el error de stock de _verificar_stock
            raise ValidationError({
                "items": [
                    f"Podés comprar hasta {MAXIMO_POR_COMPRA} unidades de cada producto "
                    f"por compra: {', '.join(excedidos)}."
                ]
            })

        # La tienda vende del Depósito; el mensaje es para el cliente (sin traslados)
        _verificar_stock(cantidades, DEPOSITO, para_cliente=True)
        lineas = _armar_lineas(cantidades)

        entrega = datos["entrega"]
        direccion = ""
        cambios_perfil = {}

        if entrega == Entrega.ENVIO:
            direccion = (
                datos.get("direccion_entrega")
                or cliente.direccion
                or ""
            ).strip()

            if not direccion:
                raise ValidationError({
                    "direccion_entrega": "Indicá una dirección de entrega."
                })

            cambios_perfil = _datos_de_contacto(cliente=cliente, datos=datos)

        # El costo sale de la tabla de tarifas por zona del servidor, no de React.
        costo_envio = Decimal("0.00")
        if entrega == Entrega.ENVIO:
            costo_envio = _costo_de_envio(datos)

        total = sum(
            (linea["subtotal"] for linea in lineas),
            Decimal("0.00"),
        ) + costo_envio

        if total <= 0:
            raise ValidationError({
                "items": "El total de la compra debe ser mayor a cero."
            })

        metadata = {
            "cliente": cliente.pk,
            "items": [
                {
                    "producto": producto.pk,
                    "cantidad": cantidad,
                }
                for producto, cantidad in cantidades.items()
            ],
            "entrega": entrega,
            "direccion_entrega": direccion or None,
            "costo_envio": str(costo_envio),
        }

        # Teléfono y documento nuevos quedan en Mi perfil (la próxima vez se
        # precargan, y el personal los ve en el envío). Valida el documento fijo
        # y que no sea de otro cliente, igual que al editar el perfil.
        if cambios_perfil:
            cliente = clientes_services.actualizar_mi_perfil(cliente=cliente, datos=cambios_perfil)

        try:
            preferencia = crear_preferencia(
                cliente=cliente,
                lineas=lineas,
                costo_envio=costo_envio,
                metadata=metadata,
            )
        except (ErrorMercadoPago, ImproperlyConfigured) as error:
            logger.exception(
                "No se pudo crear la preferencia de Mercado Pago"
            )
            raise PagoNoDisponible() from error

        return Response(
            {
                "id": preferencia["id"],
                "init_point": preferencia["init_point"],
                "total": str(total),
            },
            status=status.HTTP_201_CREATED,
        )
