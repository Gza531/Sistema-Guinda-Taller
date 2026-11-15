
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from stock.models import Stock
from .models import Categoria, Marca, Producto
from .serializers import MAXIMO_POR_COMPRA, ProductoSerializer


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


class MaximoCompraTests(TestCase):
    """La tienda recibe hasta cuántas unidades se pueden comprar, nunca el stock exacto."""

    @classmethod
    def setUpTestData(cls):
        marca = Marca.objects.create(nombre="Marca máximo")
        categoria = Categoria.objects.create(nombre="Categoría máximo")

        def producto(nombre, deposito=None, sucursal=None):
            p = Producto.objects.create(
                nombre=nombre, marca=marca, categoria=categoria,
                origen="NACIONAL", precio_venta=Decimal("1000.00"),
            )
            if deposito is not None:
                Stock.objects.create(producto=p, ubicacion="DEPOSITO", cantidad_actual=deposito, stock_minimo=1)
            if sucursal is not None:
                Stock.objects.create(producto=p, ubicacion="SUCURSAL", cantidad_actual=sucursal, stock_minimo=1)
            return p

        cls.pocos = producto("Quedan pocos", deposito=3, sucursal=50)
        cls.muchos = producto("Sobran", deposito=MAXIMO_POR_COMPRA + 15)
        cls.justo = producto("Justo el tope", deposito=MAXIMO_POR_COMPRA)
        cls.solo_salon = producto("Solo en el salón", sucursal=7)
        cls.sin_registro = producto("Sin registro de stock")

    def maximo(self, producto, cliente=None):
        respuesta = (cliente or APIClient()).get(f"/api/productos/{producto.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.data

    def test_el_limite_comercial_es_30(self):
        self.assertEqual(MAXIMO_POR_COMPRA, 30)

    def test_con_poco_stock_el_maximo_es_el_stock_del_deposito(self):
        # El salón (Sucursal) no cuenta: las ventas online salen del Depósito
        datos = self.maximo(self.pocos)
        self.assertEqual(datos["maximo_compra"], 3)
        self.assertFalse(datos["maximo_es_limite"])

    def test_con_mucho_stock_no_pasa_del_limite(self):
        for producto in (self.muchos, self.justo):
            datos = self.maximo(producto)
            self.assertEqual(datos["maximo_compra"], MAXIMO_POR_COMPRA)
            self.assertTrue(datos["maximo_es_limite"])

    def test_una_unidad_menos_que_el_limite_es_stock(self):
        Stock.objects.filter(producto=self.justo, ubicacion="DEPOSITO").update(cantidad_actual=MAXIMO_POR_COMPRA - 1)
        datos = self.maximo(self.justo)
        self.assertEqual(datos["maximo_compra"], MAXIMO_POR_COMPRA - 1)
        self.assertFalse(datos["maximo_es_limite"])

    def test_sin_stock_en_deposito_es_cero(self):
        for producto in (self.solo_salon, self.sin_registro):
            datos = self.maximo(producto)
            self.assertEqual(datos["maximo_compra"], 0)
            self.assertFalse(datos["maximo_es_limite"])

    def test_la_tienda_no_recibe_el_stock_exacto(self):
        datos = self.maximo(self.muchos)
        for campo in ("stock_deposito", "stock_sucursal", "stock_para_tienda"):
            self.assertNotIn(campo, datos)

        listado = APIClient().get("/api/productos/").data
        filas = listado["results"] if isinstance(listado, dict) else listado
        fila = next(p for p in filas if p["id_producto"] == self.muchos.pk)
        self.assertEqual(fila["maximo_compra"], MAXIMO_POR_COMPRA)
        self.assertNotIn("stock_deposito", fila)

    def test_sin_la_anotacion_del_listado_calcula_igual(self):
        # Ej. Mis favoritos, que arma su propio queryset
        self.assertEqual(ProductoSerializer(self.pocos).data["maximo_compra"], 3)
        self.assertEqual(ProductoSerializer(self.muchos).data["maximo_compra"], MAXIMO_POR_COMPRA)
        self.assertTrue(ProductoSerializer(self.muchos).data["maximo_es_limite"])
        self.assertEqual(ProductoSerializer(self.sin_registro).data["maximo_compra"], 0)
