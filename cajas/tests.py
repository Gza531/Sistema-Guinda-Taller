from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core.permissions import ENCARGADA, RESP_STOCK, VENDEDOR
from seguridad.models import Empleado, Usuario

from . import services
from .models import Caja, MetodoPago, MovimientoCaja


class CajaOnlineSinEfectivoTests(TestCase):
    """La caja online no maneja efectivo: ni al abrir, ni en movimientos, ni al cerrar."""

    @classmethod
    def setUpTestData(cls):
        cls.encargada = Usuario.objects.create_user(username="encargada_test", password="x")
        Empleado.objects.create(nombre="Eva", apellido="Paz", usuario=cls.encargada)
        cls.encargada.groups.add(Group.objects.get(name=ENCARGADA))

        cls.online = Caja.objects.create(nombre="Online test", tipo_caja=Caja.TipoCaja.ONLINE)
        cls.salon = Caja.objects.create(nombre="Salón test", tipo_caja=Caja.TipoCaja.PRESENCIAL)
        cls.efectivo = MetodoPago.efectivo()
        cls.mercado_pago = MetodoPago.mercado_pago()

    def _api(self):
        api = APIClient()
        api.force_authenticate(self.encargada)
        return api

    def _cobro_online(self, monto, tipo=MovimientoCaja.TipoMovimiento.INGRESO):
        services.registrar_movimiento_caja(
            caja=self.online, tipo_movimiento=tipo, monto=Decimal(monto),
            metodo_pago=self.mercado_pago, concepto="Cobro de prueba",
        )

    # ---------- Reglas ----------

    def test_no_se_abre_con_monto_inicial(self):
        with self.assertRaises(ValidationError):
            services.abrir_caja(caja=self.online, usuario=self.encargada, monto_inicial=Decimal("500"))

    def test_no_acepta_movimientos_en_efectivo(self):
        services.sesion_online(caja=self.online, usuario=self.encargada)
        with self.assertRaises(ValidationError):
            services.registrar_movimiento_caja(
                caja=self.online, tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO,
                monto=Decimal("100"), metodo_pago=self.efectivo, concepto="Aporte",
            )

    def test_no_acepta_metodos_no_habilitados_para_la_online(self):
        debito = MetodoPago.objects.create(nombre="Débito test")
        services.sesion_online(caja=self.online, usuario=self.encargada)
        with self.assertRaises(ValidationError):
            services.registrar_movimiento_caja(
                caja=self.online, tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO,
                monto=Decimal("100"), metodo_pago=debito, concepto="Cobro",
            )

    def test_acepta_los_metodos_habilitados(self):
        transferencia = MetodoPago.objects.create(nombre="Transferencia test", en_caja_online=True)
        services.sesion_online(caja=self.online, usuario=self.encargada)
        services.registrar_movimiento_caja(
            caja=self.online, tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO,
            monto=Decimal("100"), metodo_pago=transferencia, concepto="Cobro",
        )
        self.assertEqual(MovimientoCaja.objects.filter(metodo_pago=transferencia).count(), 1)

    def test_la_devolucion_de_una_venta_sale_con_su_metodo_aunque_ya_no_este_habilitado(self):
        from clientes.models import Cliente
        from ventas.models import Venta

        tarjeta = MetodoPago.objects.create(nombre="Crédito test")   # no habilitado para la online
        cliente = Cliente.objects.create(nombre="Lu", apellido="Gómez")
        venta = Venta.objects.create(
            cliente=cliente, usuario=self.encargada, tipo=Venta.TipoVenta.ONLINE,
            total=Decimal("100.00"), numero_comprobante="V-00000901",
        )
        services.sesion_online(caja=self.online, usuario=self.encargada)
        services.registrar_movimiento_caja(
            caja=self.online, tipo_movimiento=MovimientoCaja.TipoMovimiento.EGRESO,
            monto=Decimal("100"), metodo_pago=tarjeta, venta=venta,
        )
        self.assertEqual(MovimientoCaja.objects.filter(venta=venta).count(), 1)

    def test_efectivo_y_mercado_pago_vienen_configurados(self):
        self.assertFalse(self.efectivo.en_caja_online)
        self.assertTrue(self.mercado_pago.en_caja_online)

    # ---------- Total cobrado ----------

    def test_total_cobrado_de_la_online(self):
        sesion = services.sesion_online(caja=self.online, usuario=self.encargada)
        self._cobro_online("15000")
        self._cobro_online("2000", MovimientoCaja.TipoMovimiento.EGRESO)

        self.assertEqual(services.total_cobrado(sesion), Decimal("13000.00"))
        respuesta = self._api().get(f"/api/cajas/sesiones/{sesion.pk}/")
        self.assertEqual(respuesta.data["total_cobrado"], "13000.00")
        self.assertEqual(respuesta.data["tipo_caja"], "ONLINE")
        respuesta = self._api().get(f"/api/cajas/sesiones/{sesion.pk}/resumen/")
        self.assertEqual(respuesta.data["total_cobrado"], "13000.00")

    def test_la_presencial_no_tiene_total_cobrado(self):
        sesion = services.abrir_caja(caja=self.salon, usuario=self.encargada, monto_inicial=Decimal("1000"))
        respuesta = self._api().get(f"/api/cajas/sesiones/{sesion.pk}/")
        self.assertIsNone(respuesta.data["total_cobrado"])

    # ---------- Cierre por la API ----------

    def test_el_resumen_dice_el_tipo_de_caja(self):
        sesion = services.sesion_online(caja=self.online, usuario=self.encargada)
        respuesta = self._api().get(f"/api/cajas/sesiones/{sesion.pk}/resumen/")
        self.assertEqual(respuesta.data["tipo_caja"], "ONLINE")

    def test_la_online_se_cierra_sin_contar_efectivo(self):
        sesion = services.sesion_online(caja=self.online, usuario=self.encargada)
        self._cobro_online("15000")
        self._cobro_online("2000", MovimientoCaja.TipoMovimiento.EGRESO)  # una devolución

        respuesta = self._api().post(f"/api/cajas/sesiones/{sesion.pk}/cerrar/", {}, format="json")

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.data["sesion"]["abierta"])
        mp = respuesta.data["arqueo"]["por_metodo"][0]
        self.assertEqual((mp["metodo"], mp["ingresos"], mp["egresos"]), ("Mercado Pago", "15000.00", "2000.00"))

    def test_la_online_ignora_un_monto_final_que_llegue(self):
        sesion = services.sesion_online(caja=self.online, usuario=self.encargada)
        self._api().post(f"/api/cajas/sesiones/{sesion.pk}/cerrar/", {"monto_final": "999"}, format="json")
        sesion.refresh_from_db()
        self.assertEqual(sesion.monto_final, Decimal("0.00"))

    def test_la_presencial_sigue_pidiendo_el_efectivo_contado(self):
        sesion = services.abrir_caja(caja=self.salon, usuario=self.encargada, monto_inicial=Decimal("1000"))
        respuesta = self._api().post(f"/api/cajas/sesiones/{sesion.pk}/cerrar/", {}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("monto_final", respuesta.data)

        respuesta = self._api().post(
            f"/api/cajas/sesiones/{sesion.pk}/cerrar/", {"monto_final": "1000"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["arqueo"]["diferencia"], "0.00")


class MetodosDelSistemaTests(TestCase):
    """Efectivo y Mercado Pago los usa el sistema por nombre: no se tocan desde la API."""

    @classmethod
    def setUpTestData(cls):
        cls.encargada = Usuario.objects.create_user(username="encargada_mp", password="x")
        Empleado.objects.create(nombre="Eva", apellido="Paz", usuario=cls.encargada)
        cls.encargada.groups.add(Group.objects.get(name=ENCARGADA))
        cls.transferencia = MetodoPago.objects.create(nombre="Transferencia")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.encargada)

    def _url(self, metodo):
        return f"/api/cajas/metodos-pago/{metodo.pk}/"

    def test_mercado_pago_no_se_renombra_ni_se_da_de_baja(self):
        mp = MetodoPago.mercado_pago()
        self.assertEqual(self.api.patch(self._url(mp), {"nombre": "MP"}).status_code, 403)
        self.assertEqual(self.api.delete(self._url(mp)).status_code, 403)
        mp.refresh_from_db()
        self.assertEqual((mp.nombre, mp.estado), ("Mercado Pago", True))

    def test_efectivo_sigue_bloqueado(self):
        efectivo = MetodoPago.efectivo()
        self.assertEqual(self.api.delete(self._url(efectivo)).status_code, 403)

    def test_los_demas_se_editan_y_se_dan_de_baja(self):
        respuesta = self.api.patch(self._url(self.transferencia), {"nombre": "Transferencia bancaria"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.data["del_sistema"])
        self.assertEqual(self.api.delete(self._url(self.transferencia)).data["estado"], False)

    def test_la_lista_marca_los_del_sistema(self):
        filas = self.api.get("/api/cajas/metodos-pago/", {"page_size": 100}).data["results"]
        del_sistema = {f["nombre"] for f in filas if f["del_sistema"]}
        self.assertEqual(del_sistema, {"Efectivo", "Mercado Pago"})


class RenombrarMetodoConMovimientosTests(TestCase):
    """Un método de pago con cobros o pagos registrados no se renombra (sí se puede dar de baja)."""

    @classmethod
    def setUpTestData(cls):
        cls.encargada = Usuario.objects.create_user(username="encargada_ren", password="x")
        Empleado.objects.create(nombre="Eva", apellido="Paz", usuario=cls.encargada)
        cls.encargada.groups.add(Group.objects.get(name=ENCARGADA))

        cls.usado = MetodoPago.objects.create(nombre="Transferencia")
        cls.nuevo = MetodoPago.objects.create(nombre="Tarjeta de débto")   # con error de tipeo

        salon = Caja.objects.create(nombre="Salón ren", tipo_caja=Caja.TipoCaja.PRESENCIAL)
        services.abrir_caja(caja=salon, usuario=cls.encargada, monto_inicial=Decimal("0"))
        services.registrar_movimiento_caja(
            caja=salon, tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO,
            monto=Decimal("1000"), metodo_pago=cls.usado, concepto="Cobro de prueba",
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.encargada)

    def _patch(self, metodo, datos):
        return self.api.patch(f"/api/cajas/metodos-pago/{metodo.pk}/", datos, format="json")

    def test_con_movimientos_no_se_renombra(self):
        respuesta = self._patch(self.usado, {"nombre": "Tarjeta de crédito"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("nombre", respuesta.data)
        self.usado.refresh_from_db()
        self.assertEqual(self.usado.nombre, "Transferencia")

    def test_con_movimientos_se_puede_dar_de_baja_y_reactivar(self):
        self.assertEqual(self.api.delete(f"/api/cajas/metodos-pago/{self.usado.pk}/").data["estado"], False)
        respuesta = self._patch(self.usado, {"nombre": "Transferencia", "estado": True})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.data["estado"])

    def test_sin_movimientos_se_renombra(self):
        respuesta = self._patch(self.nuevo, {"nombre": "Tarjeta de débito"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["nombre"], "Tarjeta de débito")

    def test_la_lista_dice_cuales_tienen_movimientos(self):
        filas = self.api.get("/api/cajas/metodos-pago/", {"page_size": 100}).data["results"]
        por_nombre = {f["nombre"]: f["tiene_movimientos"] for f in filas}
        self.assertTrue(por_nombre["Transferencia"])
        self.assertFalse(por_nombre["Tarjeta de débto"])



class ResponsableDeLaSesionTests(TestCase):
    """La caja online la abre el sistema: no se muestra el usuario que pagó."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Usuario.objects.create_user(username="cliente_web", password="x")
        cls.encargada = Usuario.objects.create_user(username="encargada_resp", password="x")
        cls.online = Caja.objects.create(nombre="Online resp", tipo_caja=Caja.TipoCaja.ONLINE)
        cls.salon = Caja.objects.create(nombre="Salón resp", tipo_caja=Caja.TipoCaja.PRESENCIAL)

    def test_caja_online_no_muestra_al_cliente(self):
        from .serializers import SesionCajaSerializer
        sesion = services.sesion_online(caja=self.online, usuario=self.cliente)
        datos = SesionCajaSerializer(sesion).data
        self.assertEqual(datos["usuario_username"], "Sistema (apertura automática)")

    def test_caja_presencial_muestra_quien_la_abrio(self):
        from .serializers import SesionCajaSerializer
        sesion = services.abrir_caja(caja=self.salon, usuario=self.encargada, monto_inicial=Decimal("0"))
        datos = SesionCajaSerializer(sesion).data
        self.assertEqual(datos["usuario_username"], "encargada_resp")


class VendedorCierraCajaTests(TestCase):
    """El Vendedor abre y también cierra la caja presencial (con el arqueo)."""

    @classmethod
    def setUpTestData(cls):
        cls.vendedor = Usuario.objects.create_user(username="vendedor_test", password="x")
        Empleado.objects.create(nombre="Vera", apellido="Sosa", usuario=cls.vendedor)
        cls.vendedor.groups.add(Group.objects.get(name=VENDEDOR))

        cls.stock = Usuario.objects.create_user(username="stock_test", password="x")
        Empleado.objects.create(nombre="Saúl", apellido="Ríos", usuario=cls.stock)
        cls.stock.groups.add(Group.objects.get(name=RESP_STOCK))

        cls.salon = Caja.objects.create(nombre="Salón test", tipo_caja=Caja.TipoCaja.PRESENCIAL)

    def _cerrar(self, usuario, sesion):
        api = APIClient()
        api.force_authenticate(usuario)
        return api.post(f"/api/cajas/sesiones/{sesion.pk}/cerrar/", {"monto_final": "10000.00"}, format="json")

    def test_el_vendedor_cierra_la_caja_que_abrio(self):
        sesion = services.abrir_caja(caja=self.salon, usuario=self.vendedor, monto_inicial=Decimal("10000"))

        r = self._cerrar(self.vendedor, sesion)

        self.assertEqual(r.status_code, 200, r.data)
        sesion.refresh_from_db()
        self.assertIsNotNone(sesion.fecha_cierre)
        self.assertEqual(r.data["arqueo"]["diferencia"], "0.00")

    def test_un_rol_sin_permiso_no_puede_cerrar(self):
        sesion = services.abrir_caja(caja=self.salon, usuario=self.vendedor, monto_inicial=Decimal("10000"))

        r = self._cerrar(self.stock, sesion)

        self.assertEqual(r.status_code, 403)
        sesion.refresh_from_db()
        self.assertIsNone(sesion.fecha_cierre)
