from django.test import TestCase

# Create your tests here.
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from seguridad.models import Empleado

from .models import Cliente


URL = "/api/clientes/mi-perfil/"
URL_PASSWORD = "/api/clientes/mi-perfil/password/"
CLAVE = "Guinda.2026!"


class MiPerfilTests(TestCase):
    """GET/PATCH /api/clientes/mi-perfil/: el cliente ve y edita solo sus datos."""

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()

        cls.usuario_ana = Usuario.objects.create_user(username="ana_test", password=CLAVE, email="ana@test.com")
        cls.ana = Cliente.objects.create(
            nombre="Ana", apellido="Pérez", email="ana@test.com", usuario=cls.usuario_ana
        )

        cls.usuario_carla = Usuario.objects.create_user(username="carla_test", password=CLAVE, email="carla@test.com")
        cls.carla = Cliente.objects.create(
            nombre="Carla", apellido="Benítez", email="carla@test.com", usuario=cls.usuario_carla,
            tipo_documento=Cliente.TipoDocumento.DNI, nro_documento="30111222",
        )

        cls.usuario_empleado = Usuario.objects.create_user(username="vendedora_test", password=CLAVE)
        Empleado.objects.create(nombre="Vero", apellido="Ríos", usuario=cls.usuario_empleado)

    def _api(self, usuario):
        api = APIClient()
        api.force_authenticate(usuario)
        return api

    def _recargar(self):
        self.ana.refresh_from_db()
        self.usuario_ana.refresh_from_db()

    # ---------- Acceso ----------

    def test_sin_sesion_da_401(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_el_personal_no_entra(self):
        self.assertEqual(self._api(self.usuario_empleado).get(URL).status_code, 403)

    def test_ve_sus_datos_sin_datos_internos(self):
        respuesta = self._api(self.usuario_ana).get(URL)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["username"], "ana_test")
        self.assertEqual(respuesta.data["nombre"], "Ana")
        self.assertNotIn("estado", respuesta.data)
        self.assertNotIn("id_cliente", respuesta.data)

    # ---------- Edición ----------

    def test_edita_solo_lo_que_manda_y_limpia_espacios(self):
        respuesta = self._api(self.usuario_ana).patch(
            URL, {"telefono": " 387 555 1234 ", "direccion": "  Mitre   123 "}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200)
        self._recargar()
        self.assertEqual(self.ana.telefono, "387 555 1234")
        self.assertEqual(self.ana.direccion, "Mitre 123")
        self.assertEqual(self.ana.nombre, "Ana")  # no lo mandó: no cambia

    def test_vaciar_telefono_lo_guarda_como_null(self):
        self._api(self.usuario_ana).patch(URL, {"telefono": "387"}, format="json")
        self._api(self.usuario_ana).patch(URL, {"telefono": ""}, format="json")
        self._recargar()
        self.assertIsNone(self.ana.telefono)

    def test_el_email_se_actualiza_en_cliente_y_usuario(self):
        respuesta = self._api(self.usuario_ana).patch(URL, {"email": "  Ana.Nueva@Test.com "}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self._recargar()
        self.assertEqual(self.ana.email, "ana.nueva@test.com")
        self.assertEqual(self.usuario_ana.email, "ana.nueva@test.com")

    def test_email_de_otra_cuenta_da_400(self):
        respuesta = self._api(self.usuario_ana).patch(URL, {"email": "CARLA@test.com"}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("email", respuesta.data)

    def test_nombre_vacio_da_400(self):
        respuesta = self._api(self.usuario_ana).patch(URL, {"nombre": "   "}, format="json")
        self.assertEqual(respuesta.status_code, 400)

    def test_no_puede_llamarse_consumidor_final(self):
        respuesta = self._api(self.usuario_ana).patch(
            URL, {"nombre": "consumidor", "apellido": "FINAL"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_sin_datos_da_400(self):
        self.assertEqual(self._api(self.usuario_ana).patch(URL, {}, format="json").status_code, 400)

    def test_no_puede_cambiar_su_usuario(self):
        self._api(self.usuario_ana).patch(URL, {"username": "otra", "telefono": "1"}, format="json")
        self._recargar()
        self.assertEqual(self.usuario_ana.username, "ana_test")

    # ---------- Documento ----------

    def test_carga_el_documento_si_no_tenia(self):
        respuesta = self._api(self.usuario_ana).patch(
            URL, {"tipo_documento": "DNI", "nro_documento": "40123456"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200)
        self._recargar()
        self.assertEqual(self.ana.nro_documento, "40123456")

    def test_documento_incompleto_da_400(self):
        respuesta = self._api(self.usuario_ana).patch(URL, {"nro_documento": "40123456"}, format="json")
        self.assertEqual(respuesta.status_code, 400)

    def test_documento_de_otro_cliente_da_400(self):
        respuesta = self._api(self.usuario_ana).patch(
            URL, {"tipo_documento": "DNI", "nro_documento": "30111222"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_documento_cargado_no_se_cambia(self):
        respuesta = self._api(self.usuario_carla).patch(URL, {"nro_documento": "99999999"}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.carla.refresh_from_db()
        self.assertEqual(self.carla.nro_documento, "30111222")

    def test_reenviar_el_mismo_documento_no_molesta(self):
        respuesta = self._api(self.usuario_carla).patch(
            URL, {"tipo_documento": "DNI", "nro_documento": "30111222", "telefono": "387"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200)


class CambiarMiPasswordTests(TestCase):
    """POST /api/clientes/mi-perfil/password/"""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="ana_test", password=CLAVE)
        Cliente.objects.create(nombre="Ana", apellido="Pérez", usuario=cls.usuario)

    def _cambiar(self, actual, nueva, repetida=None):
        api = APIClient()
        api.force_authenticate(self.usuario)
        return api.post(URL_PASSWORD, {
            "password_actual": actual,
            "password_nueva": nueva,
            "password_repetida": nueva if repetida is None else repetida,
        }, format="json")

    def _clave_actual_es(self, clave):
        self.usuario.refresh_from_db()
        return self.usuario.check_password(clave)

    def test_cambia_la_contrasena(self):
        respuesta = self._cambiar(CLAVE, "Perfume.Rojo44")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(self._clave_actual_es("Perfume.Rojo44"))

    def test_actual_incorrecta_da_400(self):
        respuesta = self._cambiar("otra", "Perfume.Rojo44")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("password_actual", respuesta.data)
        self.assertTrue(self._clave_actual_es(CLAVE))

    def test_repetida_distinta_da_400(self):
        respuesta = self._cambiar(CLAVE, "Perfume.Rojo44", "Perfume.Rojo45")
        self.assertIn("password_repetida", respuesta.data)

    def test_igual_a_la_actual_da_400(self):
        self.assertIn("password_nueva", self._cambiar(CLAVE, CLAVE).data)

    def test_contrasena_debil_da_400(self):
        respuesta = self._cambiar(CLAVE, "1234")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("password_nueva", respuesta.data)
        self.assertTrue(self._clave_actual_es(CLAVE))

    def test_sin_sesion_da_401(self):
        self.assertEqual(APIClient().post(URL_PASSWORD, {}, format="json").status_code, 401)
