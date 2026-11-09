from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from cajas.models import Caja, MetodoPago
from catalogo.models import Categoria, Marca, Producto
from clientes.models import Cliente
from envios.models import Envio
from seguridad.models import Empleado
from stock.models import Stock
from ventas.models import Venta
from ventas.services import Entrega, anular_venta

from .models import DetallePedido, Pedido
from .services import entregar_pedido


E = Pedido.EstadoPedido


class AnularVentaDePedidoTests(TestCase):
    """Al anular la venta de un pedido entregado, el pedido pasa a Cancelado."""

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.encargada = Usuario.objects.create_user(username="encargada_ped", password="x")
        Empleado.objects.create(nombre="Paula", apellido="Rivas", usuario=cls.encargada)

        usuario_ana = Usuario.objects.create_user(username="ana_ped", password="x")
        cls.ana = Cliente.objects.create(nombre="Ana", apellido="Pérez", usuario=usuario_ana)

        Caja.objects.create(nombre="Caja online test", tipo_caja=Caja.TipoCaja.ONLINE)
        cls.transferencia = MetodoPago.objects.create(nombre="Transferencia")

        cls.producto = Producto.objects.create(
            nombre="Perfume pedido",
            origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("10000.00"),
            marca=Marca.objects.create(nombre="Marca pedido"),
            categoria=Categoria.objects.create(nombre="Categoría pedido"),
        )

    def setUp(self):
        self.stock = Stock.objects.create(
            producto=self.producto, ubicacion=Stock.Ubicaciones.DEPOSITO, cantidad_actual=5,
        )

    def _pedido_entregado(self, observaciones=None, entrega=Entrega.RETIRO):
        pedido = Pedido.objects.create(
            cliente=self.ana, canal=Pedido.Canal.WHATSAPP, estado=E.LISTO,
            usuario=self.encargada, observaciones=observaciones,
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=self.producto, cantidad=2, precio_referencia=Decimal("10000.00"),
        )
        envio = {"direccion_entrega": "Mitre 123, Salta", "costo_envio": Decimal("0")} if entrega == Entrega.ENVIO else {}
        entregar_pedido(
            pedido=pedido, usuario=self.encargada, entrega=entrega,
            pagos=[{"metodo_pago": self.transferencia, "monto": Decimal("20000.00")}],
            **envio,
        )
        pedido.refresh_from_db()
        return pedido, pedido.venta_set.get()

    def _anular(self, venta):
        return anular_venta(venta=venta, usuario=self.encargada, motivo="El cliente se arrepintió")

    def test_el_pedido_queda_cancelado(self):
        pedido, venta = self._pedido_entregado()
        self.assertEqual(pedido.estado, E.ENTREGADO)

        self._anular(venta)

        pedido.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(pedido.estado, E.CANCELADO)
        self.assertIn(f"venta {venta.numero_comprobante} anulada", pedido.observaciones)
        self.assertIn("El cliente se arrepintió", pedido.observaciones)
        self.assertEqual(self.stock.cantidad_actual, 5)

    def test_conserva_las_observaciones_anteriores(self):
        pedido, venta = self._pedido_entregado(observaciones="Es para regalo")
        self._anular(venta)
        pedido.refresh_from_db()
        self.assertTrue(pedido.observaciones.startswith("Es para regalo | Cancelado: venta"))

    def test_observaciones_largas_no_frenan_la_anulacion(self):
        pedido, venta = self._pedido_entregado(observaciones="x" * 495)
        self._anular(venta)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, E.CANCELADO)
        self.assertEqual(len(pedido.observaciones), 500)

    def test_si_la_anulacion_falla_el_pedido_sigue_entregado(self):
        pedido, venta = self._pedido_entregado(entrega=Entrega.ENVIO)
        Envio.objects.filter(venta=venta).update(estado=Envio.EstadoEnvio.DESPACHADO)

        with self.assertRaises(ValidationError):
            self._anular(venta)

        pedido.refresh_from_db()
        venta.refresh_from_db()
        self.assertEqual(pedido.estado, E.ENTREGADO)
        self.assertEqual(venta.estado, Venta.EstadoVenta.REGISTRADA)
