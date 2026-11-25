import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .services import crear_preferencia, ErrorMercadoPago
from requests.exceptions import ConnectionError

from types import SimpleNamespace

from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from .checkout_views import CheckoutAPIView
from .checkout_serializers import CheckoutSerializer

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalogo.models import Marca, Categoria, Producto
from clientes.models import Cliente
from stock.models import Stock

from seguridad.models import Empleado

class PreferenciaMercadoPagoTests(SimpleTestCase):

    def test_preferencia_configurada_correctamente(self):
        """Verifica que la preferencia tenga la configuración de E3."""

        variables = {
            "FRONT_URL": "https://tienda.example",
            "BACKEND_PUBLIC_URL": "https://api.tienda.example",
        }

        with patch.dict(os.environ, variables):
            with patch("pagos.services._sdk") as sdk:
                sdk.return_value.preference.return_value.create.return_value = {
                    "status": 201,
                    "response": {
                        "id": "pref_prueba",
                        "init_point": "https://example.test/pago",
                    },
                }

                resultado = crear_preferencia(
                    cliente=None,
                    lineas=[{
                        "producto": "Perfume de prueba",
                        "cantidad": 1,
                        "subtotal": 10000,
                    }],
                    costo_envio=0,
                    metadata={"cliente": 1},
                )

                datos = sdk.return_value.preference.return_value.create.call_args.args[0]

                self.assertEqual(resultado["id"], "pref_prueba")
                self.assertTrue(datos["binary_mode"])
                self.assertEqual(datos["statement_descriptor"], "GUINDAPERFUME")
                self.assertEqual(
                    datos["payment_methods"]["excluded_payment_types"],
                    [{"id": "ticket"}],
                )
                self.assertEqual(
                    datos["notification_url"],
                    "https://api.tienda.example/api/pagos/webhook/",
                )
                self.assertEqual(
                    datos["back_urls"]["success"],
                    "https://tienda.example/pago/exito",
                )

                self.assertEqual(
                    datos["auto_return"],
                    "approved",
                )

    def test_rechaza_frontend_sin_https(self):
        """Verifica que no se creen preferencias con URLs inválidas."""

        variables = {
            "FRONT_URL": "http://localhost:5173",
            "BACKEND_PUBLIC_URL": "https://api.tienda.example",
        }

        with patch.dict(os.environ, variables):
            with patch("pagos.services._sdk") as sdk:

                with self.assertRaises(ImproperlyConfigured):
                    crear_preferencia(
                        cliente=None,
                        lineas=[{
                            "producto": "Perfume de prueba",
                            "cantidad": 1,
                            "subtotal": 10000,
                        }],
                        costo_envio=0,
                        metadata={"cliente": 1},
                    )

                sdk.assert_not_called()

    def test_preferencia_con_productos_y_envio(self):
        """Verifica los importes y la metadata enviados a Mercado Pago."""

        variables = {
            "FRONT_URL": "https://tienda.example",
            "BACKEND_PUBLIC_URL": "https://api.tienda.example",
        }

        metadata = {
            "cliente": 1,
            "entrega": "ENVIO",
            "direccion_entrega": "Belgrano 123",
            "costo_envio": "3500",
        }

        with patch.dict(os.environ, variables):
            with patch("pagos.services._sdk") as sdk:
                sdk.return_value.preference.return_value.create.return_value = {
                    "status": 201,
                    "response": {
                        "id": "pref_envio_123",
                        "init_point": "https://example.test/pago",
                    },
                }

                crear_preferencia(
                    cliente=None,
                    lineas=[
                        {
                            "producto": "Perfume",
                            "cantidad": 2,
                            "subtotal": 30000,
                        },
                    ],
                    costo_envio=3500,
                    metadata=metadata,
                )

                datos = (
                    sdk.return_value.preference.return_value
                    .create.call_args.args[0]
                )

                items = datos["items"]

                self.assertEqual(len(items), 2)

                self.assertEqual(items[0]["quantity"], 2)
                self.assertEqual(items[0]["unit_price"], 15000)

                self.assertEqual(items[1]["title"], "Costo de envío")
                self.assertEqual(items[1]["unit_price"], 3500)

                total = sum(
                    item["quantity"] * item["unit_price"]
                    for item in items
                )

                self.assertEqual(total, 33500)
                self.assertEqual(datos["metadata"], metadata)

    def test_error_400_de_mercado_pago(self):
        """Verifica que un rechazo de la API genere ErrorMercadoPago."""

        variables = {
            "FRONT_URL": "https://tienda.example",
            "BACKEND_PUBLIC_URL": "https://api.tienda.example",
        }

        with patch.dict(os.environ, variables):
            with patch("pagos.services._sdk") as sdk:

                sdk.return_value.preference.return_value.create.return_value = {
                    "status": 400,
                    "response": {
                        "message": "invalid items"
                    },
                }

                with self.assertRaisesRegex(
                    ErrorMercadoPago, "HTTP 400"
                ):
                    crear_preferencia(
                        cliente=None,
                        lineas=[{
                            "producto": "Perfume",
                            "cantidad": 1,
                            "subtotal": 10000,
                        }],
                        costo_envio=0,
                        metadata={"cliente": 1},
                    )

    def test_error_de_conexion_mercado_pago(self):
        """Verifica el manejo de una falla de conexión."""

        variables = {
            "FRONT_URL": "https://tienda.example",
            "BACKEND_PUBLIC_URL": "https://api.tienda.example",
        }

        with patch.dict(os.environ, variables):
            with patch("pagos.services._sdk") as sdk:

                sdk.return_value.preference.return_value.create.side_effect = (
                    ConnectionError("Conexion simulada interrumpida")
                )

                with self.assertRaises(ErrorMercadoPago):
                    crear_preferencia(
                        cliente=None,
                        lineas=[{
                            "producto": "Perfume",
                            "cantidad": 1,
                            "subtotal": 10000,
                        }],
                        costo_envio=0,
                        metadata={"cliente": 1},
                    )


class CheckoutPermisosTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.url = reverse("pagos-checkout")
        self.vista = CheckoutAPIView.as_view()

    def test_usuario_sin_sesion(self):
        """Un usuario no autenticado no puede iniciar pagos."""

        peticion = self.factory.post(
            self.url,
            {},
            format="json"
        )

        respuesta = self.vista(peticion)

        self.assertEqual(respuesta.status_code, 401)

    def test_empleado_con_carrito_invalido(self):
        """Un empleado recibe 403 antes de validar el carrito."""

        usuario = SimpleNamespace(
            is_authenticated=True,
            is_staff=True,
            is_superuser=False,
        )

        peticion = self.factory.post(
            self.url,
            {},
            format="json"
        )

        force_authenticate(peticion, user=usuario)

        respuesta = self.vista(peticion)

        self.assertEqual(respuesta.status_code, 403)

    def test_carrito_vacio(self):
        """Un cliente no puede iniciar un checkout vacío."""

        usuario = SimpleNamespace(
            is_authenticated=True,
            is_staff=False,
            is_superuser=False,
        )

        peticion = self.factory.post(
            self.url,
            {
                "items": [],
                "entrega": "RETIRO",
            },
            format="json"
        )

        force_authenticate(peticion, user=usuario)

        with patch("pagos.checkout_views.Empleado.objects.filter") as empleados:
            empleados.return_value.exists.return_value = False

            respuesta = self.vista(peticion)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("items", respuesta.data)


class CheckoutValidacionesTests(SimpleTestCase):

    def setUp(self):
        self.producto_simulado = patch(
            "rest_framework.relations.PrimaryKeyRelatedField.to_internal_value",
            return_value=SimpleNamespace(pk=1),
        )
        self.producto_simulado.start()
        self.addCleanup(self.producto_simulado.stop)

    def test_rechaza_cantidad_cero(self):
        """No se pueden comprar cero unidades."""

        datos = {
            "items": [
                {"producto": 1, "cantidad": 0}
            ],
            "entrega": "RETIRO",
        }

        serializer = CheckoutSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("items", serializer.errors)

    def test_rechaza_entrega_invalida(self):
        """Solo se aceptan los tipos de entrega definidos."""

        datos = {
            "items": [
                {"producto": 1, "cantidad": 1}
            ],
            "entrega": "OTRA",
        }

        serializer = CheckoutSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("entrega", serializer.errors)

    def test_rechaza_retiro_con_direccion(self):
        """El retiro en tienda no necesita dirección."""

        datos = {
            "items": [
                {"producto": 1, "cantidad": 1}
            ],
            "entrega": "RETIRO",
            "direccion_entrega": "Calle de prueba 123",
        }

        serializer = CheckoutSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn("direccion_entrega", serializer.errors)


class CheckoutStockTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Creamos un usuario y su ficha de cliente.
        cls.usuario = get_user_model().objects.create_user(
            username="cliente_prueba_e4",
            password="clave_temporal_e4",
        )

        cls.cliente = Cliente.objects.create(
            nombre="Cliente",
            apellido="Prueba",
            usuario=cls.usuario,
            estado=True,
        )

        # Creamos marca, categoria y producto.
        marca = Marca.objects.create(
            nombre="Marca E4"
        )

        categoria = Categoria.objects.create(
            nombre="Perfumes E4"
        )

        cls.producto = Producto.objects.create(
            nombre="Perfume de prueba",
            origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("10000.00"),
            marca=marca,
            categoria=categoria,
            estado=True,
        )

        # El producto tiene 3 unidades en deposito.
        cls.stock = Stock.objects.create(
            producto=cls.producto,
            ubicacion=Stock.Ubicaciones.DEPOSITO,
            cantidad_actual=3,
        )

    def setUp(self):
        self.cliente_api = APIClient()
        self.cliente_api.force_authenticate(
            user=self.usuario
        )
        self.url = reverse("pagos-checkout")

    def comprar(self, cantidad):
        return self.cliente_api.post(
            self.url,
            {
                "items": [
                    {
                        "producto": self.producto.pk,
                        "cantidad": cantidad,
                    }
                ],
                "entrega": "RETIRO",
            },
            format="json",
        )

    def test_stock_insuficiente_no_inicia_pago(self):
        """No se inicia Mercado Pago si faltan unidades."""

        with patch(
            "pagos.checkout_views.crear_preferencia"
        ) as mercado_pago:

            respuesta = self.comprar(5)

            self.assertEqual(respuesta.status_code, 400)
            self.assertIn("items", respuesta.data)

            mercado_pago.assert_not_called()

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, 3)

    def test_el_mensaje_de_stock_es_para_el_cliente(self):
        """Sin ubicaciones ni traslados: eso es interno del local."""
        Stock.objects.create(
            producto=self.producto, ubicacion=Stock.Ubicaciones.SUCURSAL, cantidad_actual=8,
        )
        respuesta = self.comprar(5)
        mensaje = " ".join(respuesta.data["items"])
        self.assertIn("solo quedan 3 unidades", mensaje)
        self.assertNotIn("traslado", mensaje)
        self.assertNotIn("Sucursal", mensaje)

    def test_disponible_en_la_tienda_cuenta_solo_el_deposito(self):
        sin_deposito = Producto.objects.create(
            nombre="Solo en el salón", origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("5000.00"), marca=self.producto.marca,
            categoria=self.producto.categoria, estado=True,
        )
        Stock.objects.create(
            producto=sin_deposito, ubicacion=Stock.Ubicaciones.SUCURSAL, cantidad_actual=8,
        )
        catalogo = APIClient()
        self.assertFalse(catalogo.get(f"/api/productos/{sin_deposito.pk}/").data["disponible"])
        self.assertTrue(catalogo.get(f"/api/productos/{self.producto.pk}/").data["disponible"])

    def test_stock_suficiente_no_descuenta_unidades(self):
        """Iniciar el checkout no reserva ni descuenta stock."""

        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={
                "id": "pref_stock_e4",
                "init_point": "https://example.test/pago",
            },
        ) as mercado_pago:

            respuesta = self.comprar(2)

            self.assertEqual(respuesta.status_code, 201)
            self.assertEqual(
                respuesta.data["id"],
                "pref_stock_e4",
            )
            self.assertEqual(
                Decimal(respuesta.data["total"]),
                Decimal("20000.00"),
            )

            mercado_pago.assert_called_once()

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, 3)

    def test_metadata_para_el_webhook(self):
        """La metadata respeta el contrato que lee el webhook (G3)."""

        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={
                "id": "p",
                "init_point": "https://example.test/pago",
            },
        ) as mercado_pago:
            self.comprar(2)

        self.assertEqual(
            mercado_pago.call_args.kwargs["metadata"],
            {
                "cliente": self.cliente.pk,
                "items": [
                    {
                        "producto": self.producto.pk,
                        "cantidad": 2,
                    }
                ],
                "entrega": "RETIRO",
                "direccion_entrega": None,
                "costo_envio": "0.00",
            },
        )

    def test_error_mercado_pago_devuelve_503(self):
        """Una falla de Mercado Pago no debe afectar el stock."""

        with patch(
            "pagos.checkout_views.crear_preferencia",
            side_effect=ErrorMercadoPago(
                "Error simulado de Mercado Pago"
            ),
        ) as mercado_pago:

            respuesta = self.comprar(2)

        self.assertEqual(respuesta.status_code, 503)
        self.assertIn("detail", respuesta.data)
        mercado_pago.assert_called_once()

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, 3)

    def test_envio_sin_direccion_devuelve_400(self):
        """Un envío sin dirección no puede iniciar un pago."""

        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={
                "id": "pref_simulada",
                "init_point": "https://example.test/pago",
            },
        ) as mercado_pago:

            respuesta = self.cliente_api.post(
                self.url,
                {
                    "items": [
                        {
                            "producto": self.producto.pk,
                            "cantidad": 1,
                        }
                    ],
                    "entrega": "ENVIO",
                },
                format="json",
            )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("direccion_entrega", respuesta.data)
        mercado_pago.assert_not_called()

    def test_envio_con_direccion_y_costo(self):
        """El envío suma su costo y usa la dirección del cliente."""

        self.cliente.direccion = "Belgrano 123"
        # El envío también pide teléfono y documento (si están en el perfil, se usan esos)
        self.cliente.telefono = "387 5551234"
        self.cliente.tipo_documento = Cliente.TipoDocumento.DNI
        self.cliente.nro_documento = "38124567"
        self.cliente.save()

        # El costo sale de la tarifa por zona (Salta Capital: 3500)
        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={
                "id": "pref_envio_e4",
                "init_point": "https://example.test/pago",
            },
        ) as mercado_pago:

            respuesta = self.cliente_api.post(
                self.url,
                {
                    "items": [
                        {
                            "producto": self.producto.pk,
                            "cantidad": 1,
                        }
                    ],
                    "entrega": "ENVIO",
                    "provincia": "Salta",
                    "codigo_postal": "4400",
                },
                format="json",
            )

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(
            Decimal(respuesta.data["total"]),
            Decimal("13500.00"),
        )

        mercado_pago.assert_called_once()
        argumentos = mercado_pago.call_args.kwargs

        self.assertEqual(
            argumentos["costo_envio"],
            Decimal("3500"),
        )
        self.assertEqual(
            argumentos["metadata"]["direccion_entrega"],
            "Belgrano 123",
        )
        self.assertEqual(
            argumentos["metadata"]["costo_envio"],
            "3500.00",
        )

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, 3)

    def test_empleado_real_no_puede_comprar(self):
        """Un empleado registrado no puede utilizar el checkout."""

        Empleado.objects.create(
            nombre="Empleado",
            apellido="Prueba",
            usuario=self.usuario,
        )

        self.assertFalse(self.usuario.is_staff)

        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={
                "id": "pref_simulada",
                "init_point": "https://example.test/pago",
            },
        ) as mercado_pago:

            respuesta = self.comprar(1)

        self.assertEqual(respuesta.status_code, 403)
        mercado_pago.assert_not_called()

    def test_usuario_sin_ficha_cliente_recibe_403(self):
        """Un usuario sin ficha de cliente no puede comprar."""

        usuario_sin_cliente = get_user_model().objects.create_user(
            username="sin_ficha_e4",
            password="clave_temporal_e4",
        )

        self.cliente_api.force_authenticate(
            user=usuario_sin_cliente
        )

        with patch(
            "pagos.checkout_views.crear_preferencia"
        ) as mercado_pago:

            respuesta = self.comprar(1)

        self.assertEqual(respuesta.status_code, 403)
        mercado_pago.assert_not_called()

class ConfiguracionTiendaTests(SimpleTestCase):
    """GET /api/pagos/configuracion/: la tabla de tarifas de envío que muestra la tienda."""

    URL = "/api/pagos/configuracion/"

    def test_devuelve_las_tarifas_sin_sesion(self):
        respuesta = APIClient().get(self.URL)
        self.assertEqual(respuesta.status_code, 200)
        tarifas = respuesta.data["tarifas_envio"]
        self.assertEqual(
            [(t["zona"], t["costo"]) for t in tarifas],
            [
                ("Salta Capital", "3500.00"),
                ("Resto de Salta", "6000.00"),
                ("NOA", "8500.00"),
                ("Resto del país", "12000.00"),
            ],
        )

    def test_solo_lectura(self):
        self.assertEqual(APIClient().post(self.URL, {}).status_code, 405)


class TarifaEnvioTests(SimpleTestCase):
    """pagos/tarifas.py y GET /api/pagos/costo-envio/: costo según la zona de destino."""

    URL = "/api/pagos/costo-envio/"

    def test_zonas(self):
        from .tarifas import tarifa_envio
        casos = [
            ("Salta", "4400", "Salta Capital", "3500.00"),
            ("Salta", "A4400ABC", "Salta Capital", "3500.00"),
            ("Salta", "4427", "Resto de Salta", "6000.00"),
            ("Jujuy", "4600", "NOA", "8500.00"),
            ("Santiago del Estero", "4200", "NOA", "8500.00"),
            ("Córdoba", "5000", "Resto del país", "12000.00"),
            ("Buenos Aires", "4400", "Resto del país", "12000.00"),
        ]
        for provincia, cp, zona, costo in casos:
            with self.subTest(provincia=provincia, cp=cp):
                tarifa = tarifa_envio(provincia, cp)
                self.assertEqual(tarifa["zona"], zona)
                self.assertEqual(tarifa["costo"], Decimal(costo))

    def test_endpoint_sin_sesion(self):
        respuesta = APIClient().get(self.URL, {"provincia": "Tucumán", "codigo_postal": "4000"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, {"zona": "NOA", "costo": "8500.00"})

    def test_endpoint_rechaza_destino_invalido(self):
        self.assertEqual(APIClient().get(self.URL, {"provincia": "Salta"}).status_code, 400)
        self.assertEqual(
            APIClient().get(self.URL, {"provincia": "Narnia", "codigo_postal": "4400"}).status_code, 400
        )
        self.assertEqual(
            APIClient().get(self.URL, {"provincia": "Salta", "codigo_postal": "44"}).status_code, 400
        )


class CheckoutMaximoPorCompraTests(TestCase):
    """La tienda vende hasta 30 unidades de cada producto por compra, aunque haya más stock."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="cliente_maximo", password="clave_maximo")
        Cliente.objects.create(nombre="Cliente", apellido="Maximo", usuario=cls.usuario, estado=True)

        marca = Marca.objects.create(nombre="Marca máximo")
        categoria = Categoria.objects.create(nombre="Categoría máximo")
        cls.producto = Producto.objects.create(
            nombre="Perfume con mucho stock", origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("1000.00"), marca=marca, categoria=categoria, estado=True,
        )
        Stock.objects.create(producto=cls.producto, ubicacion=Stock.Ubicaciones.DEPOSITO, cantidad_actual=100)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(user=self.usuario)

    def comprar(self, *cantidades):
        items = [{"producto": self.producto.pk, "cantidad": c} for c in cantidades]
        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={"id": "pref_maximo", "init_point": "https://example.test/pago"},
        ) as mercado_pago:
            respuesta = self.api.post(reverse("pagos-checkout"), {"items": items, "entrega": "RETIRO"}, format="json")
        return respuesta, mercado_pago

    def test_30_unidades_se_pueden_comprar(self):
        respuesta, mercado_pago = self.comprar(30)
        self.assertEqual(respuesta.status_code, 201)
        mercado_pago.assert_called_once()

    def test_31_unidades_se_rechazan_aunque_haya_stock(self):
        respuesta, mercado_pago = self.comprar(31)
        self.assertEqual(respuesta.status_code, 400)
        mensaje = " ".join(respuesta.data["items"])
        self.assertIn("hasta 30 unidades", mensaje)
        self.assertIn("Perfume con mucho stock", mensaje)
        self.assertNotIn("100", mensaje)  # no revela el stock
        mercado_pago.assert_not_called()

    def test_el_limite_suma_el_producto_repetido(self):
        respuesta, mercado_pago = self.comprar(20, 11)
        self.assertEqual(respuesta.status_code, 400)
        mercado_pago.assert_not_called()

    def test_el_limite_se_revisa_antes_que_el_stock(self):
        Stock.objects.filter(producto=self.producto).update(cantidad_actual=10)
        respuesta, _ = self.comprar(31)
        mensaje = " ".join(respuesta.data["items"])
        self.assertIn("hasta 30 unidades", mensaje)
        self.assertNotIn("quedan", mensaje)

    def test_sin_stock_en_deposito_no_se_compra_aunque_haya_en_el_salon(self):
        Stock.objects.filter(producto=self.producto).update(cantidad_actual=0)
        Stock.objects.create(producto=self.producto, ubicacion=Stock.Ubicaciones.SUCURSAL, cantidad_actual=50)
        respuesta, mercado_pago = self.comprar(1)
        self.assertEqual(respuesta.status_code, 400)
        mercado_pago.assert_not_called()


class CheckoutDatosDeContactoTests(TestCase):
    """El envío a domicilio necesita teléfono y documento; se guardan en el perfil del cliente."""

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.usuario = Usuario.objects.create_user(username="cliente_contacto", password="clave_contacto")
        cls.cliente = Cliente.objects.create(
            nombre="Lucía", apellido="Fernández", usuario=cls.usuario, estado=True,
            direccion="Belgrano 123, Salta",
        )
        Cliente.objects.create(
            nombre="Otro", apellido="Cliente", estado=True,
            tipo_documento=Cliente.TipoDocumento.DNI, nro_documento="30111222",
        )

        marca = Marca.objects.create(nombre="Marca contacto")
        categoria = Categoria.objects.create(nombre="Categoría contacto")
        cls.producto = Producto.objects.create(
            nombre="Perfume contacto", origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("1000.00"), marca=marca, categoria=categoria, estado=True,
        )
        Stock.objects.create(producto=cls.producto, ubicacion=Stock.Ubicaciones.DEPOSITO, cantidad_actual=10)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(user=self.usuario)

    def comprar(self, entrega="ENVIO", **extra):
        cuerpo = {"items": [{"producto": self.producto.pk, "cantidad": 1}], "entrega": entrega}
        if entrega == "ENVIO":
            cuerpo.update(provincia="Salta", codigo_postal="4400")
        cuerpo.update(extra)
        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={"id": "pref_contacto", "init_point": "https://example.test/pago"},
        ) as mercado_pago:
            respuesta = self.api.post(reverse("pagos-checkout"), cuerpo, format="json")
        self.cliente.refresh_from_db()
        return respuesta, mercado_pago

    def comprado(self):
        from ventas.models import Venta
        Venta.objects.create(
            cliente=self.cliente, usuario=self.usuario, tipo=Venta.TipoVenta.ONLINE,
            total=1000, numero_comprobante="V-00009999",
        )

    def test_envio_sin_telefono_ni_documento_da_400(self):
        respuesta, mercado_pago = self.comprar()
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("telefono", respuesta.data)
        self.assertIn("nro_documento", respuesta.data)
        mercado_pago.assert_not_called()

    def test_los_datos_nuevos_quedan_en_el_perfil(self):
        respuesta, mercado_pago = self.comprar(telefono="387 555-1234", nro_documento="38.124.567")
        self.assertEqual(respuesta.status_code, 201)
        mercado_pago.assert_called_once()
        self.assertEqual(self.cliente.telefono, "387 555-1234")
        self.assertEqual(self.cliente.tipo_documento, Cliente.TipoDocumento.DNI)
        self.assertEqual(self.cliente.nro_documento, "38124567")

    def test_si_no_los_manda_usa_los_del_perfil(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(
            telefono="3875550000", tipo_documento="DNI", nro_documento="38124567"
        )
        respuesta, _ = self.comprar()
        self.assertEqual(respuesta.status_code, 201)

    def test_telefono_o_documento_invalidos(self):
        for extra, campo in (
            ({"telefono": "123", "nro_documento": "38124567"}, "telefono"),
            ({"telefono": "llamame", "nro_documento": "38124567"}, "telefono"),
            ({"telefono": "3875551234", "nro_documento": "38A24567"}, "nro_documento"),
            ({"telefono": "3875551234", "nro_documento": "12345"}, "nro_documento"),
        ):
            respuesta, mercado_pago = self.comprar(**extra)
            self.assertEqual(respuesta.status_code, 400, extra)
            self.assertIn(campo, respuesta.data)
            mercado_pago.assert_not_called()

    def test_documento_de_otro_cliente_da_400(self):
        respuesta, mercado_pago = self.comprar(telefono="3875551234", nro_documento="30111222")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("nro_documento", respuesta.data)
        mercado_pago.assert_not_called()

    def test_con_compras_el_documento_no_se_cambia(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(
            telefono="3875550000", tipo_documento="DNI", nro_documento="38124567"
        )
        self.comprado()

        respuesta, mercado_pago = self.comprar(nro_documento="38124568")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("nro_documento", respuesta.data)
        mercado_pago.assert_not_called()
        self.assertEqual(self.cliente.nro_documento, "38124567")

        # El mismo documento sí pasa, y el teléfono se puede cambiar siempre
        respuesta, _ = self.comprar(nro_documento="38124567", telefono="3875559999")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(self.cliente.telefono, "3875559999")

    def test_con_compras_pero_sin_documento_lo_puede_cargar(self):
        self.comprado()
        respuesta, _ = self.comprar(telefono="3875551234", nro_documento="38124567")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(self.cliente.nro_documento, "38124567")

    def test_con_cuit_en_el_perfil_valida_11_numeros(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(telefono="3875550000", tipo_documento="CUIT")
        respuesta, _ = self.comprar(nro_documento="38124567")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("CUIT", str(respuesta.data["nro_documento"]))

        respuesta, _ = self.comprar(nro_documento="20-38124567-3")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(self.cliente.nro_documento, "20381245673")

    def test_retiro_no_los_pide_ni_toca_el_perfil(self):
        respuesta, _ = self.comprar(entrega="RETIRO", telefono="3875551234", nro_documento="38124567")
        self.assertEqual(respuesta.status_code, 201)
        self.assertIsNone(self.cliente.telefono)
        self.assertIsNone(self.cliente.nro_documento)


class CheckoutCostoPorZonaTests(TestCase):
    """El checkout cobra el envío según la zona del destino (pagos/tarifas.py)."""

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.usuario = Usuario.objects.create_user(username="cliente_zona", password="clave_zona")
        Cliente.objects.create(
            nombre="Ana", apellido="Zona", usuario=cls.usuario, estado=True,
            direccion="Belgrano 123", telefono="387 5551234",
            tipo_documento=Cliente.TipoDocumento.DNI, nro_documento="38124568",
        )
        marca = Marca.objects.create(nombre="Marca zona")
        categoria = Categoria.objects.create(nombre="Categoría zona")
        cls.producto = Producto.objects.create(
            nombre="Perfume zona", origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("1000.00"), marca=marca, categoria=categoria, estado=True,
        )
        Stock.objects.create(producto=cls.producto, ubicacion=Stock.Ubicaciones.DEPOSITO, cantidad_actual=10)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(user=self.usuario)

    def comprar(self, **destino):
        cuerpo = {"items": [{"producto": self.producto.pk, "cantidad": 1}], "entrega": "ENVIO", **destino}
        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={"id": "pref_zona", "init_point": "https://example.test/pago"},
        ) as mercado_pago:
            respuesta = self.api.post(reverse("pagos-checkout"), cuerpo, format="json")
        return respuesta, mercado_pago

    def test_cobra_la_tarifa_de_la_zona(self):
        casos = [
            ({"provincia": "Salta", "codigo_postal": "4400"}, "3500.00"),
            ({"provincia": "Salta", "codigo_postal": "4427"}, "6000.00"),
            ({"provincia": "Jujuy", "codigo_postal": "4600"}, "8500.00"),
            ({"provincia": "Córdoba", "codigo_postal": "X5000ABC"}, "12000.00"),
        ]
        for destino, costo in casos:
            with self.subTest(**destino):
                respuesta, mercado_pago = self.comprar(**destino)
                self.assertEqual(respuesta.status_code, 201)
                argumentos = mercado_pago.call_args.kwargs
                self.assertEqual(argumentos["costo_envio"], Decimal(costo))
                self.assertEqual(argumentos["metadata"]["costo_envio"], costo)
                self.assertEqual(Decimal(respuesta.data["total"]), Decimal("1000.00") + Decimal(costo))

    def test_envio_sin_provincia_ni_codigo_postal_da_400(self):
        respuesta, mercado_pago = self.comprar()
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("provincia", respuesta.data)
        self.assertIn("codigo_postal", respuesta.data)
        mercado_pago.assert_not_called()

    def test_destino_invalido_da_400(self):
        respuesta, mercado_pago = self.comprar(provincia="Narnia", codigo_postal="4400")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("provincia", respuesta.data)
        respuesta, mercado_pago = self.comprar(provincia="Salta", codigo_postal="44")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("codigo_postal", respuesta.data)
        mercado_pago.assert_not_called()

    def test_retiro_no_cobra_envio(self):
        with patch(
            "pagos.checkout_views.crear_preferencia",
            return_value={"id": "pref_zona", "init_point": "https://example.test/pago"},
        ) as mercado_pago:
            respuesta = self.api.post(
                reverse("pagos-checkout"),
                {"items": [{"producto": self.producto.pk, "cantidad": 1}], "entrega": "RETIRO"},
                format="json",
            )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(mercado_pago.call_args.kwargs["costo_envio"], Decimal("0.00"))
