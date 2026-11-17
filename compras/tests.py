from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from cajas.models import Caja, MetodoPago, MovimientoCaja
from cajas.services import abrir_caja, sesion_online
from proveedores.models import Proveedor

from .models import Compra
from .services import pagar_compra


class PagarCompraTests(TestCase):
    """Las compras se pagan desde una caja presencial, nunca desde la caja online."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="encargada_compras", password="x")
        cls.proveedor = Proveedor.objects.create(razon_social="Distribuidora Norte", cuit="30-71234567-8")
        cls.salon = Caja.objects.create(nombre="Salón compras", tipo_caja=Caja.TipoCaja.PRESENCIAL)
        cls.online = Caja.objects.create(nombre="Online compras", tipo_caja=Caja.TipoCaja.ONLINE)
        cls.transferencia = MetodoPago.objects.create(nombre="Transferencia", en_caja_online=True)

    def setUp(self):
        self.compra = Compra.objects.create(
            proveedor=self.proveedor, usuario=self.usuario, total=Decimal("50000.00"),
        )

    def test_no_se_paga_desde_la_caja_online(self):
        sesion_online(caja=self.online, usuario=self.usuario)
        with self.assertRaises(ValidationError) as error:
            pagar_compra(compra=self.compra, caja=self.online, metodo_pago=self.transferencia)
        self.assertIn("caja", error.exception.detail)
        self.assertFalse(MovimientoCaja.objects.filter(compra=self.compra).exists())

    def test_se_paga_desde_una_caja_presencial(self):
        abrir_caja(caja=self.salon, usuario=self.usuario, monto_inicial=Decimal("0"))
        pagar_compra(compra=self.compra, caja=self.salon, metodo_pago=self.transferencia)
        movimiento = MovimientoCaja.objects.get(compra=self.compra)
        self.assertEqual((movimiento.tipo_movimiento, movimiento.monto), ("EGRESO", Decimal("50000.00")))
