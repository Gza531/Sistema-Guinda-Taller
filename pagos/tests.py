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
        self.cliente.save()

        with patch.dict(
            os.environ,
            {"MP_COSTO_ENVIO": "3500"},
        ):
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
            "3500",
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
