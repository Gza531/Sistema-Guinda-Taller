from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from cajas.models import Caja, MetodoPago
from catalogo.models import Categoria, Marca, Producto
from clientes.models import Cliente
from seguridad.models import Empleado
from stock.models import Stock
from ventas.services import Entrega, registrar_venta_online

from . import services
from .models import Envio


class CostoCobradoTests(TestCase):
    """
    El costo de un envío que se cobró en la venta queda fijo: el envío tiene que
    mostrar lo mismo que se le cobró al cliente. El de un envío armado a mano
    (venta que no cobró envío) es informativo y se puede editar.
    """

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.encargada = Usuario.objects.create_user(username="encargada_envio", password="x")
        Empleado.objects.create(nombre="Paula", apellido="Rivas", usuario=cls.encargada)
        cls.cliente = Cliente.objects.create(nombre="Ana", apellido="Pérez", direccion="Belgrano 123, Salta")

        Caja.objects.create(nombre="Caja online envíos", tipo_caja=Caja.TipoCaja.ONLINE)
        cls.transferencia = MetodoPago.objects.create(nombre="Transferencia", en_caja_online=True)

        cls.producto = Producto.objects.create(
            nombre="Perfume envío",
            origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("10000.00"),
            marca=Marca.objects.create(nombre="Marca envío"),
            categoria=Categoria.objects.create(nombre="Categoría envío"),
        )

    def setUp(self):
        Stock.objects.create(producto=self.producto, ubicacion=Stock.Ubicaciones.DEPOSITO, cantidad_actual=10)

    def _venta(self, entrega, costo_envio=None):
        total = Decimal("10000.00") + (costo_envio or Decimal("0.00"))
        return registrar_venta_online(
            usuario=self.encargada, cliente=self.cliente, entrega=entrega,
            items=[{"producto": self.producto, "cantidad": 1}],
            pagos=[{"metodo_pago": self.transferencia, "monto": total}],
            direccion_entrega="Belgrano 123, Salta" if entrega == Entrega.ENVIO else None,
            costo_envio=costo_envio,
        )

    def test_venta_con_envio_deja_el_costo_cobrado_fijo(self):
        venta = self._venta(Entrega.ENVIO, costo_envio=Decimal("6000.00"))
        envio = Envio.objects.get(venta=venta)
        self.assertTrue(envio.costo_cobrado)
        self.assertEqual(envio.costo, Decimal("6000.00"))

        with self.assertRaises(ValidationError) as error:
            services.actualizar_envio(envio=envio, costo=Decimal("3000.00"))
        self.assertIn("se cobró en la venta", str(error.exception.detail))

        envio.refresh_from_db()
        self.assertEqual(envio.costo, Decimal("6000.00"))

    def test_un_envio_cobrado_no_se_elimina(self):
        venta = self._venta(Entrega.ENVIO, costo_envio=Decimal("6000.00"))
        envio = Envio.objects.get(venta=venta)
        with self.assertRaises(ValidationError) as error:
            services.eliminar_envio(envio=envio)
        self.assertIn("anulá la venta", str(error.exception.detail))
        self.assertTrue(Envio.objects.filter(pk=envio.pk).exists())

    def test_los_demas_datos_se_siguen_corrigiendo(self):
        venta = self._venta(Entrega.ENVIO, costo_envio=Decimal("6000.00"))
        envio = Envio.objects.get(venta=venta)

        # Mandar el mismo costo (como hace el formulario) no es un cambio
        envio = services.actualizar_envio(
            envio=envio, costo=Decimal("6000.00"),
            direccion_entrega="Belgrano 125, Salta", empresa_transporte="Andreani",
        )
        self.assertEqual(envio.direccion_entrega, "Belgrano 125, Salta")
        self.assertEqual(envio.empresa_transporte, "Andreani")

    def test_envio_armado_a_mano_es_editable(self):
        venta = self._venta(Entrega.RETIRO)
        envio = services.crear_envio(venta=venta, costo=Decimal("2500.00"))
        self.assertFalse(envio.costo_cobrado)

        envio = services.actualizar_envio(envio=envio, costo=Decimal("3000.00"))
        self.assertEqual(envio.costo, Decimal("3000.00"))

        services.eliminar_envio(envio=envio)
        self.assertFalse(Envio.objects.filter(pk=envio.pk).exists())
