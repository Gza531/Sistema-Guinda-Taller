from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from catalogo.models import Categoria, Marca, Producto
from envios.models import Envio
from pedidos.models import Pedido
from stock.models import Stock
from ventas.models import Venta


class CargarDemoTests(TestCase):
    """manage.py cargar_demo: datos de demo con los productos que ya están cargados."""

    def setUp(self):
        get_user_model().objects.create_superuser(username="admin_demo", password="x")

    def _cargar(self):
        call_command("cargar_demo", stdout=StringIO())

    def test_carga_la_demo_con_los_productos_existentes(self):
        with self.assertRaises(CommandError):   # todavía no hay productos
            self._cargar()

        marca = Marca.objects.create(nombre="Marca demo")
        categoria = Categoria.objects.create(nombre="Categoría demo")
        for i, precio in enumerate([9000, 15000, 180000, 60000, 32000, 250000]):
            Producto.objects.create(
                nombre=f"Producto {i}", marca=marca, categoria=categoria,
                origen=Producto.OrigenProducto.IMPORTADO, precio_venta=Decimal(precio),
            )

        self._cargar()

        self.assertEqual(Venta.objects.filter(estado=Venta.EstadoVenta.ANULADA).count(), 1)
        self.assertEqual(Envio.objects.filter(costo_cobrado=True).count(), 6)
        self.assertEqual(
            set(Pedido.objects.values_list("estado", flat=True)),
            {"PENDIENTE", "RESERVADO", "LISTO", "ENTREGADO", "CANCELADO"},
        )
        self.assertFalse(Stock.objects.filter(cantidad_actual__lt=0).exists())
        self.assertEqual(Marca.objects.count(), 1)   # no crea marcas ni categorías
        self.assertTrue(get_user_model().objects.get(username="vguzman").check_password("Guinda.2026!"))

        ventas = Venta.objects.count()
        self._cargar()   # la segunda vez no hace nada
        self.assertEqual(Venta.objects.count(), ventas)

    def test_usa_lo_que_ya_cargaron_a_mano(self):
        from cajas import services as cajas_services
        from cajas.models import AperturaCierreCaja, Caja
        from seguridad import services as seguridad_services
        from core.permissions import DUENA

        admin = get_user_model().objects.get(username="admin_demo")
        marca = Marca.objects.create(nombre="Dior")
        categoria = Categoria.objects.create(nombre="Perfumes")
        for i in range(6):
            Producto.objects.create(
                nombre=f"Perfume {i}", marca=marca, categoria=categoria,
                origen=Producto.OrigenProducto.NACIONAL, precio_venta=Decimal("20000"),
            )
        # La Dueña cargada con otro usuario y la caja del salón ya abierta
        seguridad_services.crear_empleado(
            actor=admin, username="valeria", password="Guinda.2026!", roles=[DUENA],
            nombre="Valeria", apellido="Guzmán", dni="28456123",
        )
        salon = Caja.objects.create(nombre="Mostrador", tipo_caja=Caja.TipoCaja.PRESENCIAL)
        cajas_services.abrir_caja(caja=salon, usuario=admin, monto_inicial=Decimal("50000"))

        self._cargar()

        self.assertFalse(get_user_model().objects.filter(username="vguzman").exists())
        self.assertEqual(Caja.objects.filter(tipo_caja=Caja.TipoCaja.PRESENCIAL).count(), 1)
        self.assertEqual(AperturaCierreCaja.objects.filter(caja=salon).count(), 1)
        self.assertTrue(Venta.objects.filter(usuario__username="fcruz").exists())
