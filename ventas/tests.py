from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from cajas.models import Caja, MetodoPago, MovimientoCaja
from catalogo.models import Categoria, Marca, Producto
from clientes.models import Cliente
from envios.models import Envio
from pagos.services import ErrorMercadoPago
from seguridad.models import Empleado
from stock.models import Stock

from .models import DetalleVenta, Venta
from .services import Entrega, anular_venta, registrar_venta_online


URL = "/api/ventas/mis-compras/"


class MisComprasTests(TestCase):
    """GET /api/ventas/mis-compras/: cada cliente ve solo sus compras."""

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()

        cls.usuario_ana = Usuario.objects.create_user(username="ana_test", password="x")
        cls.ana = Cliente.objects.create(nombre="Ana", apellido="Pérez", usuario=cls.usuario_ana)

        cls.usuario_carla = Usuario.objects.create_user(username="carla_test", password="x")
        cls.carla = Cliente.objects.create(nombre="Carla", apellido="Benítez", usuario=cls.usuario_carla)

        cls.usuario_empleado = Usuario.objects.create_user(username="vendedora_test", password="x")
        Empleado.objects.create(nombre="Vero", apellido="Ríos", usuario=cls.usuario_empleado)

        cls.producto = Producto.objects.create(
            nombre="Perfume de prueba",
            origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("10000.00"),
            marca=Marca.objects.create(nombre="Marca test"),
            categoria=Categoria.objects.create(nombre="Categoría test"),
        )

        # Ana: una compra web con envío, una en el local y una web anulada
        cls.web = cls._venta(cls.ana, "V-00000001", Venta.TipoVenta.ONLINE, cantidad=2)
        Envio.objects.create(venta=cls.web, direccion_entrega="Mitre 123", costo=Decimal("2500.00"),
                             estado=Envio.EstadoEnvio.DESPACHADO, empresa_transporte="Andreani",
                             codigo_seguimiento="AND-999")
        cls.local = cls._venta(cls.ana, "V-00000002", Venta.TipoVenta.PRESENCIAL, cantidad=1)
        cls.anulada = cls._venta(cls.ana, "V-00000003", Venta.TipoVenta.ONLINE, cantidad=1,
                                 estado=Venta.EstadoVenta.ANULADA)

        # Carla: una compra (Ana no la tiene que ver)
        cls.de_carla = cls._venta(cls.carla, "V-00000004", Venta.TipoVenta.ONLINE, cantidad=1)

    @classmethod
    def _venta(cls, cliente, numero, tipo, cantidad, estado=Venta.EstadoVenta.REGISTRADA):
        subtotal = cls.producto.precio_venta * cantidad
        venta = Venta.objects.create(
            cliente=cliente, usuario=cliente.usuario, tipo=tipo, estado=estado,
            total=subtotal, numero_comprobante=numero, observaciones="nota interna",
        )
        DetalleVenta.objects.create(
            venta=venta, producto=cls.producto, cantidad=cantidad,
            precio_unitario=cls.producto.precio_venta, descuento_aplicado=Decimal("0"),
            subtotal=subtotal,
        )
        return venta

    def _cliente_api(self, usuario):
        api = APIClient()
        api.force_authenticate(usuario)
        return api

    def test_sin_sesion_da_401(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_el_personal_no_entra(self):
        respuesta = self._cliente_api(self.usuario_empleado).get(URL)
        self.assertEqual(respuesta.status_code, 403)

    def test_ve_solo_sus_compras_incluidas_local_y_anuladas(self):
        respuesta = self._cliente_api(self.usuario_ana).get(URL)
        self.assertEqual(respuesta.status_code, 200)
        numeros = {compra["numero_comprobante"] for compra in respuesta.data["results"]}
        self.assertEqual(numeros, {"V-00000001", "V-00000002", "V-00000003"})

    def test_listado_trae_envio_y_cantidad(self):
        respuesta = self._cliente_api(self.usuario_ana).get(URL)
        web = next(c for c in respuesta.data["results"] if c["id_venta"] == self.web.pk)
        self.assertEqual(web["cantidad_productos"], 2)
        self.assertEqual(web["envio"]["estado"], "DESPACHADO")
        self.assertEqual(web["envio"]["codigo_seguimiento"], "AND-999")
        local = next(c for c in respuesta.data["results"] if c["id_venta"] == self.local.pk)
        self.assertIsNone(local["envio"])

    def test_detalle_trae_marca_volumen_e_imagen(self):
        respuesta = self._cliente_api(self.usuario_ana).get(f"{URL}{self.web.pk}/")
        detalle = respuesta.data["detalles"][0]
        self.assertEqual(detalle["marca_nombre"], "Marca test")
        self.assertIn("volumen", detalle)
        self.assertIsNone(detalle["imagen"])  # el producto de prueba no tiene fotos

    def test_detalle_trae_productos_y_no_datos_internos(self):
        respuesta = self._cliente_api(self.usuario_ana).get(f"{URL}{self.web.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["detalles"][0]["producto_nombre"], "Perfume de prueba")
        for interno in ("usuario", "observaciones", "mp_payment_id", "cliente"):
            self.assertNotIn(interno, respuesta.data)

    def test_compra_ajena_da_404(self):
        respuesta = self._cliente_api(self.usuario_ana).get(f"{URL}{self.de_carla.pk}/")
        self.assertEqual(respuesta.status_code, 404)

    def test_no_se_puede_modificar(self):
        api = self._cliente_api(self.usuario_ana)
        self.assertEqual(api.delete(f"{URL}{self.web.pk}/").status_code, 405)
        self.assertEqual(api.post(URL, {}, format="json").status_code, 405)

    def test_con_envio_trae_solo_las_compras_con_envio(self):
        respuesta = self._cliente_api(self.usuario_ana).get(URL, {"con_envio": "1"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([c["numero_comprobante"] for c in respuesta.data["results"]], ["V-00000001"])
        envio = respuesta.data["results"][0]["envio"]
        self.assertEqual((envio["estado"], envio["codigo_seguimiento"]), ("DESPACHADO", "AND-999"))

    def test_con_envio_no_trae_envios_de_otro_cliente(self):
        Envio.objects.create(venta=self.de_carla, direccion_entrega="Belgrano 9", costo=Decimal("0"))
        respuesta = self._cliente_api(self.usuario_ana).get(URL, {"con_envio": "1"})
        self.assertNotIn("V-00000004", [c["numero_comprobante"] for c in respuesta.data["results"]])

    def test_muestra_el_envio_vigente_si_hubo_uno_devuelto(self):
        venta = self._venta(self.ana, "V-00000005", Venta.TipoVenta.ONLINE, cantidad=1)
        Envio.objects.create(venta=venta, direccion_entrega="Mitre 123", costo=Decimal("0"),
                             estado=Envio.EstadoEnvio.DEVUELTO, codigo_seguimiento="VIEJO-1")
        Envio.objects.create(venta=venta, direccion_entrega="Mitre 123", costo=Decimal("0"),
                             estado=Envio.EstadoEnvio.EN_TRANSITO, codigo_seguimiento="NUEVO-2")

        filas = self._cliente_api(self.usuario_ana).get(URL, {"con_envio": "1"}).data["results"]
        de_la_venta = [c for c in filas if c["numero_comprobante"] == "V-00000005"]
        self.assertEqual(len(de_la_venta), 1)   # una fila por compra, aunque tenga dos envíos
        self.assertEqual(de_la_venta[0]["envio"]["codigo_seguimiento"], "NUEVO-2")

        detalle = self._cliente_api(self.usuario_ana).get(f"{URL}{venta.pk}/").data
        self.assertEqual(detalle["envio"]["estado"], "EN_TRANSITO")


# ---------------- Anulación con devolución por Mercado Pago ----------------

class AnularVentaMercadoPagoTests(TestCase):
    """
    anular_venta con una venta cobrada por Mercado Pago. Mercado Pago se simula
    (no se llama a la API real): así se prueban los tres casos posibles.
    """

    def setUp(self):
        Usuario = get_user_model()
        self.encargada = Usuario.objects.create_user(username="encargada_test", password="x")
        Empleado.objects.create(nombre="Paula", apellido="Rivas", usuario=self.encargada)

        usuario_ana = Usuario.objects.create_user(username="ana_mp", password="x")
        ana = Cliente.objects.create(nombre="Ana", apellido="Pérez", usuario=usuario_ana)

        Caja.objects.create(nombre="Caja online test", tipo_caja=Caja.TipoCaja.ONLINE)

        self.producto = Producto.objects.create(
            nombre="Perfume MP",
            origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("10000.00"),
            marca=Marca.objects.create(nombre="Marca MP"),
            categoria=Categoria.objects.create(nombre="Categoría MP"),
        )
        self.stock = Stock.objects.create(
            producto=self.producto, ubicacion=Stock.Ubicaciones.DEPOSITO, cantidad_actual=5,
        )

        # Como la registra el webhook: a nombre del cliente, cobrada por Mercado Pago
        self.venta = registrar_venta_online(
            usuario=usuario_ana,
            cliente=ana,
            items=[{"producto": self.producto, "cantidad": 2}],
            pagos=[{"metodo_pago": MetodoPago.mercado_pago(), "monto": Decimal("20000.00")}],
            entrega=Entrega.ENVIO,
            direccion_entrega="Mitre 123, Salta",
            costo_envio=Decimal("0.00"),
            mp_payment_id="123456",
        )

    def _anular(self):
        return anular_venta(venta=self.venta, usuario=self.encargada, motivo="El cliente se arrepintió")

    def _estado(self):
        self.venta.refresh_from_db()
        self.stock.refresh_from_db()
        envio = Envio.objects.get(venta=self.venta)
        egresos = MovimientoCaja.objects.filter(
            venta=self.venta, tipo_movimiento=MovimientoCaja.TipoMovimiento.EGRESO
        ).count()
        return self.venta.estado, self.stock.cantidad_actual, envio.estado, egresos

    @patch("ventas.services.reembolsar")
    def test_devolucion_ok_anula_todo(self, reembolsar):
        self._anular()
        reembolsar.assert_called_once_with("123456")
        self.assertEqual(self._estado(), ("ANULADA", 5, "CANCELADO", 1))

    @patch("ventas.services.obtener_pago", return_value={"status": "refunded"})
    @patch("ventas.services.reembolsar", side_effect=ErrorMercadoPago("HTTP 400"))
    def test_si_ya_estaba_devuelto_anula_igual(self, reembolsar, obtener_pago):
        # Ej.: la devolución se hizo a mano desde Mercado Pago antes de anular
        self._anular()
        obtener_pago.assert_called_once_with("123456")
        self.assertEqual(self._estado(), ("ANULADA", 5, "CANCELADO", 1))

    @patch("ventas.services.obtener_pago", return_value={"status": "approved"})
    @patch("ventas.services.reembolsar", side_effect=ErrorMercadoPago("HTTP 401"))
    def test_si_falla_la_devolucion_no_se_anula_nada(self, reembolsar, obtener_pago):
        with self.assertRaises(ValidationError) as error:
            self._anular()
        self.assertIn("mercado_pago", error.exception.detail)
        # Todo como antes: la venta sigue registrada, el stock descontado, el envío pendiente
        self.assertEqual(self._estado(), ("REGISTRADA", 3, "PENDIENTE", 0))