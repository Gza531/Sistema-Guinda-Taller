
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from catalogo.models import Categoria, Marca, Producto
from core.permissions import DUENA, VENDEDOR
from promociones import services
from promociones.models import Promocion, PromocionProducto
from promociones.services import _validar
from seguridad.models import Empleado


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


def _empleado(username, rol):
    usuario = get_user_model().objects.create_user(username=username, password="x")
    usuario.groups.add(Group.objects.get(name=rol))
    Empleado.objects.create(nombre=username.title(), apellido="Test", usuario=usuario)
    return usuario


class ReactivarPromocionTests(TestCase):
    """Una promoción desactivada se reactiva editándola con estado=True,
    siempre que su fecha de fin sea hoy o posterior."""

    @classmethod
    def setUpTestData(cls):
        cls.duena = _empleado("duena_test", DUENA)
        cls.vendedora = _empleado("vendedora_test", VENDEDOR)
        cls.producto = Producto.objects.create(
            nombre="Perfume de prueba",
            origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("10000.00"),
            marca=Marca.objects.create(nombre="Marca test"),
            categoria=Categoria.objects.create(nombre="Categoría test"),
        )

    def setUp(self):
        self.hoy = timezone.localdate()
        # Desactivada y ya vencida: se usó el mes pasado
        self.promo = Promocion.objects.create(
            nombre="Día del Padre",
            tipo_descuento=Promocion.TipoDescuento.PORCENTAJE,
            valor_descuento=Decimal("10"),
            fecha_inicio=self.hoy - timedelta(days=40),
            fecha_fin=self.hoy - timedelta(days=10),
            estado=False,
        )
        PromocionProducto.objects.create(promocion=self.promo, producto=self.producto)

    def _patch(self, usuario, datos):
        api = APIClient()
        api.force_authenticate(usuario)
        return api.patch(f"/api/promociones/promociones/{self.promo.pk}/", datos, format="json")

    def test_reactiva_con_fechas_nuevas(self):
        r = self._patch(self.duena, {
            "estado": True,
            "fecha_inicio": str(self.hoy),
            "fecha_fin": str(self.hoy + timedelta(days=15)),
        })

        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["estado"])
        self.promo.refresh_from_db()
        self.assertTrue(self.promo.estado)
        self.assertIn(self.promo, services.vigentes())

    def test_no_reactiva_si_la_fecha_de_fin_ya_paso(self):
        r = self._patch(self.duena, {"estado": True})

        self.assertEqual(r.status_code, 400)
        self.assertIn("fecha_fin", r.data)
        self.promo.refresh_from_db()
        self.assertFalse(self.promo.estado)

    def test_editar_sin_estado_no_la_reactiva(self):
        r = self._patch(self.duena, {"nombre": "Día del Padre 2026"})

        self.assertEqual(r.status_code, 200, r.data)
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.nombre, "Día del Padre 2026")
        self.assertFalse(self.promo.estado)

    def test_rol_sin_permiso_no_puede_reactivar(self):
        r = self._patch(self.vendedora, {
            "estado": True,
            "fecha_fin": str(self.hoy + timedelta(days=15)),
        })

        self.assertEqual(r.status_code, 403)
        self.promo.refresh_from_db()
        self.assertFalse(self.promo.estado)
