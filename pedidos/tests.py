from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from cajas.models import Caja, MetodoPago
from catalogo.models import Categoria, Marca, Producto
from clientes.models import Cliente
from envios.models import Envio
from seguridad.models import Empleado
from stock.models import Stock
from stock.services import registrar_reposicion
from ventas.models import Venta
from ventas.services import Entrega, anular_venta, registrar_venta_online

from . import services
from .models import DetallePedido, Pedido
from .reservas import reservadas
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
        cls.transferencia = MetodoPago.objects.create(nombre="Transferencia", en_caja_online=True)

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


class ReservaDeStockTests(TestCase):
    """
    Los pedidos se pagan por adelantado: solo se toman con stock en el Depósito
    y sus unidades quedan apartadas hasta entregarlos o cancelarlos.
    """

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.encargada = Usuario.objects.create_user(username="encargada_res", password="x")
        Empleado.objects.create(nombre="Paula", apellido="Rivas", usuario=cls.encargada)
        cls.ana = Cliente.objects.create(
            nombre="Ana", apellido="Pérez", usuario=Usuario.objects.create_user(username="ana_res", password="x"),
        )
        cls.luis = Cliente.objects.create(nombre="Luis", apellido="Gómez")

        Caja.objects.create(nombre="Caja online reserva", tipo_caja=Caja.TipoCaja.ONLINE)
        cls.transferencia = MetodoPago.objects.create(nombre="Transferencia", en_caja_online=True)

        cls.producto = Producto.objects.create(
            nombre="Perfume reservado",
            origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("10000.00"),
            marca=Marca.objects.create(nombre="Marca reserva"),
            categoria=Categoria.objects.create(nombre="Categoría reserva"),
        )

    def setUp(self):
        self.deposito = Stock.objects.create(
            producto=self.producto, ubicacion=Stock.Ubicaciones.DEPOSITO, cantidad_actual=3,
        )

    def _pedido(self, cliente, cantidad):
        return services.crear_pedido(
            cliente=cliente, canal=Pedido.Canal.WHATSAPP, usuario=self.encargada,
            items=[{"producto": self.producto, "cantidad": cantidad}],
        )

    def _venta_online(self, cantidad, pedido=None):
        return registrar_venta_online(
            usuario=self.encargada, cliente=self.luis, entrega=Entrega.RETIRO,
            items=[{"producto": self.producto, "cantidad": cantidad}],
            pagos=[{"metodo_pago": self.transferencia, "monto": Decimal("10000.00") * cantidad}],
        )

    def test_no_se_toma_un_pedido_sin_stock(self):
        with self.assertRaises(ValidationError) as error:
            self._pedido(self.ana, 4)
        self.assertIn("hay 3 disponibles", str(error.exception.detail))
        self.assertFalse(Pedido.objects.exists())

    def test_las_unidades_de_un_pedido_no_las_toma_otro(self):
        self._pedido(self.ana, 2)
        self.assertEqual(reservadas(self.producto), 2)
        with self.assertRaises(ValidationError):
            self._pedido(self.luis, 2)
        self._pedido(self.luis, 1)   # queda una libre

    def test_las_unidades_de_un_pedido_no_se_venden_online(self):
        self._pedido(self.ana, 2)
        with self.assertRaises(ValidationError):
            self._venta_online(2)
        self._venta_online(1)
        self.deposito.refresh_from_db()
        self.assertEqual(self.deposito.cantidad_actual, 2)

    def test_el_pedido_se_entrega_con_sus_propias_unidades(self):
        pedido = self._pedido(self.ana, 3)
        services.cambiar_estado(pedido=pedido, estado=E.RESERVADO)
        services.cambiar_estado(pedido=pedido, estado=E.LISTO)
        services.entregar_pedido(
            pedido=pedido, usuario=self.encargada, entrega=Entrega.RETIRO,
            pagos=[{"metodo_pago": self.transferencia, "monto": Decimal("30000.00")}],
        )
        self.deposito.refresh_from_db()
        self.assertEqual(self.deposito.cantidad_actual, 0)
        self.assertEqual(reservadas(self.producto), 0)

    def test_al_cancelar_se_liberan_las_unidades(self):
        pedido = self._pedido(self.ana, 3)
        services.cancelar_pedido(pedido=pedido, motivo="No transfirió")
        self.assertEqual(reservadas(self.producto), 0)
        self._venta_online(3)

    def test_no_se_trasladan_al_salon_las_unidades_apartadas(self):
        self._pedido(self.ana, 2)
        with self.assertRaises(ValidationError):
            registrar_reposicion(
                producto=self.producto, origen=Stock.Ubicaciones.DEPOSITO, cantidad=2, usuario=self.encargada,
            )
        registrar_reposicion(
            producto=self.producto, origen=Stock.Ubicaciones.DEPOSITO, cantidad=1, usuario=self.encargada,
        )

    def test_la_tienda_no_ofrece_las_unidades_apartadas(self):
        self._pedido(self.ana, 3)
        producto = APIClient().get(f"/api/productos/{self.producto.pk}/").data
        self.assertFalse(producto["disponible"])
        self.assertEqual(producto["maximo_compra"], 0)

    def test_ya_no_existe_el_estado_en_espera_de_stock(self):
        pedido = self._pedido(self.ana, 1)
        with self.assertRaises(ValidationError):
            services.cambiar_estado(pedido=pedido, estado="EN_ESPERA_STOCK")

    def test_el_stock_del_deposito_informa_lo_apartado(self):
        self._pedido(self.ana, 2)
        api = APIClient()
        api.force_authenticate(get_user_model().objects.create_superuser(username="admin_res", password="x"))
        fila = api.get("/api/stock/existencias/", {"ubicacion": "DEPOSITO"}).data["results"][0]
        self.assertEqual((fila["cantidad_actual"], fila["reservado"], fila["disponible"]), (3, 2, 1))
        producto = api.get(f"/api/productos/{self.producto.pk}/").data
        self.assertEqual((producto["stock_deposito"], producto["stock_reservado"]), (3, 2))
