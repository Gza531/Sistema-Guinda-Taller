import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from catalogo.models import Categoria, Marca, Producto
from clientes.models import Cliente
from core.permissions import DUENA, ENCARGADA, VENDEDOR
from seguridad.models import Empleado

from .contexto import como_usuario
from .models import Auditoria

PASSWORD = "Clave.Segura.2026"


def _empleado(username, rol):
    usuario = get_user_model().objects.create_user(username=username, password=PASSWORD)
    usuario.groups.add(Group.objects.get(name=rol))
    Empleado.objects.create(nombre=username.title(), apellido="Test", usuario=usuario)
    return usuario


class AuditoriaTests(TestCase):
    """Lo que se hace sin request (como este setUp) no se audita: no hay responsable."""

    @classmethod
    def setUpTestData(cls):
        cls.duena = _empleado("duena_test", DUENA)
        cls.encargada = _empleado("encargada_test", ENCARGADA)
        cls.vendedora = _empleado("vendedora_test", VENDEDOR)
        cls.producto = Producto.objects.create(
            nombre="Perfume de prueba",
            origen=Producto.OrigenProducto.NACIONAL,
            precio_venta=Decimal("10000.00"),
            marca=Marca.objects.create(nombre="Marca test"),
            categoria=Categoria.objects.create(nombre="Categoría test"),
        )

    def _api(self, usuario):
        api = APIClient()
        api.force_authenticate(usuario)
        return api

    @staticmethod
    def _ultimo(**filtros):
        return Auditoria.objects.filter(**filtros).order_by("-id_auditoria").first()

    # ---------- Registro automático ----------

    def test_sin_request_no_se_registra(self):
        self.assertEqual(Auditoria.objects.count(), 0)

    def test_alta_registra_insert_con_sus_datos(self):
        respuesta = self._api(self.duena).post("/api/marcas/", {"nombre": "Dior"}, format="json")
        self.assertEqual(respuesta.status_code, 201)
        registro = self._ultimo(tabla_afectada="marcas")
        self.assertEqual(registro.accion, "INSERT")
        self.assertEqual(registro.usuario, self.duena)
        self.assertEqual(json.loads(registro.datos_nuevos)["nombre"], "Dior")
        self.assertIsNone(registro.datos_previos)

    def test_modificacion_guarda_solo_lo_que_cambio(self):
        url = f"/api/productos/{self.producto.pk}/"
        respuesta = self._api(self.duena).patch(url, {"precio_venta": "12500.00"}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        registro = self._ultimo(tabla_afectada="productos", accion="UPDATE")
        self.assertEqual(json.loads(registro.datos_previos), {"precio_venta": "10000.00"})
        self.assertEqual(json.loads(registro.datos_nuevos), {"precio_venta": "12500.00"})

    def test_baja_logica_queda_como_update_de_estado(self):
        respuesta = self._api(self.duena).delete(f"/api/productos/{self.producto.pk}/")
        self.assertIn(respuesta.status_code, (200, 204))
        registro = self._ultimo(tabla_afectada="productos", accion="UPDATE")
        self.assertEqual(json.loads(registro.datos_previos), {"estado": True})
        self.assertEqual(json.loads(registro.datos_nuevos), {"estado": False})

    def test_cambio_de_password_no_guarda_el_hash(self):
        empleado = self.vendedora.empleado
        url = f"/api/seguridad/empleados/{empleado.pk}/cambiar-password/"
        respuesta = self._api(self.duena).post(url, {"password": "Otra.Clave.2026"}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        registro = self._ultimo(tabla_afectada="usuarios", accion="UPDATE")
        self.assertEqual(json.loads(registro.datos_nuevos), {"password": "(modificada)"})
        self.assertNotIn("pbkdf2", registro.datos_previos + registro.datos_nuevos)

    def test_cambio_de_roles_queda_en_un_solo_registro(self):
        empleado = self.vendedora.empleado
        url = f"/api/seguridad/empleados/{empleado.pk}/"
        antes = Auditoria.objects.count()
        respuesta = self._api(self.duena).patch(url, {"roles": [ENCARGADA]}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        de_roles = [
            json.loads(r.datos_nuevos) for r in Auditoria.objects.all()[antes:]
            if r.datos_nuevos and "roles" in r.datos_nuevos
        ]
        self.assertEqual(de_roles, [{"roles": [ENCARGADA]}])

    def test_como_usuario_registra_a_nombre_del_responsable(self):
        with como_usuario(self.vendedora):
            Marca.objects.create(nombre="Desde webhook")
        self.assertEqual(self._ultimo(tabla_afectada="marcas").usuario, self.vendedora)

    # ---------- Login y logout ----------

    def test_login_correcto_registra_login(self):
        respuesta = APIClient().post("/api/login/", {"username": "duena_test", "password": PASSWORD},
                                     format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._ultimo(accion="LOGIN").usuario, self.duena)

    def test_login_fallido_no_registra(self):
        APIClient().post("/api/login/", {"username": "duena_test", "password": "mala"}, format="json")
        self.assertFalse(Auditoria.objects.filter(accion="LOGIN").exists())

    def test_logout_registra_logout(self):
        respuesta = self._api(self.encargada).post("/api/logout/")
        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(self._ultimo(accion="LOGOUT").usuario, self.encargada)

    def test_los_clientes_no_se_auditan(self):
        usuario = get_user_model().objects.create_user(username="cliente_test", password=PASSWORD)
        Cliente.objects.create(nombre="Ana", apellido="Pérez", usuario=usuario)
        api = APIClient()
        respuesta = api.post("/api/login/", {"username": "cliente_test", "password": PASSWORD},
                             format="json")
        self.assertEqual(respuesta.status_code, 200)
        api.force_authenticate(usuario)
        self.assertEqual(api.post("/api/logout/").status_code, 204)
        with como_usuario(usuario):
            Marca.objects.create(nombre="Hecha por un cliente")
        self.assertEqual(list(Auditoria.objects.values_list("accion", "tabla_afectada")), [])
        
    def test_logout_sin_sesion_da_401(self):
        self.assertEqual(APIClient().post("/api/logout/").status_code, 401)

    # ---------- Consulta ----------

    def test_solo_la_duena_consulta(self):
        url = "/api/auditoria/auditorias/"
        self.assertEqual(self._api(self.duena).get(url).status_code, 200)
        self.assertEqual(self._api(self.encargada).get(url).status_code, 403)
        self.assertEqual(self._api(self.vendedora).get(url).status_code, 403)

    def test_filtros_y_datos_como_objeto(self):
        api = self._api(self.duena)
        api.post("/api/marcas/", {"nombre": "Kenzo"}, format="json")
        api.post("/api/logout/")
        respuesta = api.get("/api/auditoria/auditorias/?accion=insert&tabla=marcas")
        self.assertEqual(respuesta.data["count"], 1)
        self.assertEqual(respuesta.data["results"][0]["datos_nuevos"]["nombre"], "Kenzo")
        self.assertEqual(api.get("/api/auditoria/auditorias/?desde=30-10-2026").status_code, 400)

    def test_no_se_puede_modificar_por_api(self):
        # 403: la acción no está en "permisos" (cerrado por defecto); 405 si lo estuviera
        api = self._api(self.duena)
        self.assertIn(api.post("/api/auditoria/auditorias/", {}, format="json").status_code, (403, 405))
