
from datetime import date
from decimal import Decimal

from rest_framework.exceptions import ValidationError
from django.test import SimpleTestCase

from promociones.services import _validar


class ValidacionPorcentajeTests(SimpleTestCase):

    def validar_porcentaje(self, valor):
        _validar(
            tipo_descuento="PORCENTAJE",
            valor_descuento=Decimal(valor),
            fecha_inicio=date(2026, 11, 1),
            fecha_fin=date(2026, 11, 30),
            productos=[object()],
        )

    def test_acepta_porcentajes_enteros(self):
        for valor in ("1", "15", "100", "15.00"):
            with self.subTest(valor=valor):
                self.validar_porcentaje(valor)

    def test_rechaza_porcentajes_invalidos(self):
        for valor in ("0", "-10", "0.5", "15.5", "99.9", "101"):
            with self.subTest(valor=valor):
                with self.assertRaises(ValidationError):
                    self.validar_porcentaje(valor)
