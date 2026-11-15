
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from stock.models import Stock
from .models import Categoria, Marca, Producto


class ProductoStockTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="admin_prueba_stock",
            email="admin_stock@example.com",
            password="PruebaSegura123!"
        )

        marca = Marca.objects.create(nombre="Marca de prueba")
        categoria = Categoria.objects.create(nombre="Perfumes de prueba")

        cls.producto = Producto.objects.create(
            nombre="Perfume con stock",
            marca=marca,
            categoria=categoria,
            origen="IMPORTADO",
            precio_venta=Decimal("15000.00"),
        )

        cls.producto_sin_stock = Producto.objects.create(
            nombre="Perfume sin stock",
            marca=marca,
            categoria=categoria,
            origen="NACIONAL",
            precio_venta=Decimal("10000.00"),
        )

        Stock.objects.create(
            producto=cls.producto,
            ubicacion="SUCURSAL",
            cantidad_actual=12,
            stock_minimo=2,
        )

        Stock.objects.create(
            producto=cls.producto,
            ubicacion="DEPOSITO",
            cantidad_actual=8,
            stock_minimo=2,
        )

    def obtener_productos(self, cliente):
        respuesta = cliente.get("/api/productos/")
        self.assertEqual(respuesta.status_code, 200)

        datos = respuesta.data
        return datos["results"] if isinstance(datos, dict) and "results" in datos else datos

    def test_personal_ve_stock_por_ubicacion(self):
        cliente = APIClient()
        cliente.force_authenticate(user=self.usuario)

        productos = self.obtener_productos(cliente)
        producto = next(
            p for p in productos
            if p["id_producto"] == self.producto.pk
        )

        self.assertEqual(producto["stock_sucursal"], 12)
        self.assertEqual(producto["stock_deposito"], 8)

    def test_producto_sin_stock_devuelve_ceros(self):
        cliente = APIClient()
        cliente.force_authenticate(user=self.usuario)

        productos = self.obtener_productos(cliente)
        producto = next(
            p for p in productos
            if p["id_producto"] == self.producto_sin_stock.pk
        )

        self.assertEqual(producto["stock_sucursal"], 0)
        self.assertEqual(producto["stock_deposito"], 0)

    def test_publico_no_recibe_stock_interno(self):
        cliente = APIClient()

        productos = self.obtener_productos(cliente)
        producto = next(
            p for p in productos
            if p["id_producto"] == self.producto.pk
        )

        self.assertNotIn("stock_sucursal", producto)
        self.assertNotIn("stock_deposito", producto)
