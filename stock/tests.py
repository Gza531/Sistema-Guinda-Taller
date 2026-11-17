
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalogo.models import Categoria, Marca, Producto
from .models import MovimientoStock, Stock


class HistorialStockTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="admin_prueba_movimientos",
            email="movimientos@example.com",
            password="PruebaSegura123!"
        )

        marca = Marca.objects.create(nombre="Marca historial")
        categoria = Categoria.objects.create(nombre="Categoría historial")

        cls.producto_uno = Producto.objects.create(
            nombre="Perfume uno",
            marca=marca,
            categoria=categoria,
            origen="IMPORTADO",
            precio_venta=Decimal("10000.00"),
        )

        cls.producto_dos = Producto.objects.create(
            nombre="Perfume dos",
            marca=marca,
            categoria=categoria,
            origen="NACIONAL",
            precio_venta=Decimal("20000.00"),
        )

        stock_uno = Stock.objects.create(
            producto=cls.producto_uno,
            ubicacion="SUCURSAL",
            cantidad_actual=10,
        )

        stock_dos = Stock.objects.create(
            producto=cls.producto_dos,
            ubicacion="DEPOSITO",
            cantidad_actual=5,
        )

        MovimientoStock.objects.create(
            stock=stock_uno,
            usuario=cls.usuario,
            tipo_movimiento="ENTRADA",
            cantidad=10,
            motivo="Movimiento del producto uno",
        )

        MovimientoStock.objects.create(
            stock=stock_dos,
            usuario=cls.usuario,
            tipo_movimiento="ENTRADA",
            cantidad=5,
            motivo="Movimiento del producto dos",
        )

    def setUp(self):
        self.cliente = APIClient()
        self.cliente.force_authenticate(user=self.usuario)

    def obtener_movimientos(self, parametros=None):
        respuesta = self.cliente.get(
            "/api/stock/movimientos/",
            parametros or {}
        )

        self.assertEqual(respuesta.status_code, 200)

        datos = respuesta.data
        return datos["results"] if isinstance(datos, dict) and "results" in datos else datos

    def test_historial_filtrado_por_producto(self):
        movimientos = self.obtener_movimientos({
            "producto": self.producto_uno.pk
        })

        self.assertEqual(len(movimientos), 1)
        self.assertEqual(
            movimientos[0]["producto_nombre"],
            "Perfume uno"
        )

    def test_historial_sin_filtro(self):
        movimientos = self.obtener_movimientos()

        self.assertEqual(len(movimientos), 2)

    def test_producto_sin_movimientos(self):
        movimientos = self.obtener_movimientos({
            "producto": 999999
        })

        self.assertEqual(len(movimientos), 0)

    def test_identificador_invalido(self):
        respuesta = self.cliente.get(
            "/api/stock/movimientos/",
            {"producto": "abc"}
        )

        self.assertEqual(respuesta.status_code, 400)

    # ---------- Filtros de Stock · Movimientos ----------

    def test_filtra_por_ubicacion(self):
        movimientos = self.obtener_movimientos({"ubicacion": "deposito"})
        self.assertEqual([m["producto_nombre"] for m in movimientos], ["Perfume dos"])

    def test_filtra_por_tipo(self):
        self.assertEqual(len(self.obtener_movimientos({"tipo": "ENTRADA"})), 2)
        self.assertEqual(len(self.obtener_movimientos({"tipo": "SALIDA"})), 0)

    def test_busca_por_nombre_de_producto(self):
        movimientos = self.obtener_movimientos({"buscar": "uno"})
        self.assertEqual([m["producto_nombre"] for m in movimientos], ["Perfume uno"])

    def test_tipo_o_ubicacion_invalidos(self):
        self.assertEqual(self.cliente.get("/api/stock/movimientos/", {"tipo": "ROBO"}).status_code, 400)
        self.assertEqual(self.cliente.get("/api/stock/movimientos/", {"ubicacion": "CASA"}).status_code, 400)
