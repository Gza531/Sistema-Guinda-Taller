from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalogo.models import Categoria, Marca, Producto
from clientes.models import Cliente
from envios.models import Envio
from seguridad.models import Empleado

from .models import DetalleVenta, Venta


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