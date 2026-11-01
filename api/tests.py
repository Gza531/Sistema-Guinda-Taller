import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from clientes.models import Cliente
from seguridad.models import Empleado


PEDIR = "/api/recuperar-password/"
CONFIRMAR = "/api/recuperar-password/confirmar/"
NUEVA = "Otra.Clave.2026"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperarPasswordTests(TestCase):
    """Recuperar la contraseña por mail: solo clientes, link de un solo uso."""

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.ana = Usuario.objects.create_user(username="ana_rp", password="Vieja.Clave.2026", email="ana@mail.com")
        Cliente.objects.create(nombre="Ana", apellido="Pérez", email="ana@mail.com", usuario=cls.ana)

        cls.vendedora = Usuario.objects.create_user(username="vero_rp", password="x", email="vero@guinda.com")
        Empleado.objects.create(nombre="Vero", apellido="Ríos", usuario=cls.vendedora)

    def setUp(self):
        cache.clear()   # el límite de pedidos usa la caché: cada test arranca de cero
        self.api = APIClient()

    def _pedir(self, email):
        return self.api.post(PEDIR, {"email": email}, format="json")

    def _link(self):
        """uid y token del último mail enviado."""
        uid, token = re.search(r"/restablecer/([^/\s]+)/([^/\s]+)", mail.outbox[-1].body).groups()
        return uid, token

    def test_cliente_recibe_el_link(self):
        respuesta = self._pedir("ANA@mail.com")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@mail.com"])
        self.assertIn("/restablecer/", mail.outbox[0].body)

    def test_email_inexistente_responde_igual_sin_mandar_nada(self):
        respuesta = self._pedir("nadie@mail.com")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, self._pedir("ana@mail.com").data)
        self.assertEqual(len(mail.outbox), 1)   # solo el de Ana

    def test_el_personal_no_recupera_por_mail(self):
        self.assertEqual(self._pedir("vero@guinda.com").status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_restablecer_cambia_la_password_y_el_link_es_de_un_solo_uso(self):
        self._pedir("ana@mail.com")
        uid, token = self._link()

        respuesta = self.api.post(CONFIRMAR, {"uid": uid, "token": token, "password": NUEVA}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password(NUEVA))

        otra_vez = self.api.post(CONFIRMAR, {"uid": uid, "token": token, "password": "Tercera.Clave.2026"}, format="json")
        self.assertEqual(otra_vez.status_code, 400)

    def test_link_falso_da_400(self):
        respuesta = self.api.post(CONFIRMAR, {"uid": "xx", "token": "yy", "password": NUEVA}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("detail", respuesta.data)

    def test_password_debil_da_400_y_no_cambia(self):
        self._pedir("ana@mail.com")
        uid, token = self._link()
        respuesta = self.api.post(CONFIRMAR, {"uid": uid, "token": token, "password": "123"}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("password", respuesta.data)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password("Vieja.Clave.2026"))

    def test_limite_de_5_pedidos_por_hora(self):
        for _ in range(5):
            self.assertEqual(self._pedir("ana@mail.com").status_code, 200)
        self.assertEqual(self._pedir("ana@mail.com").status_code, 429)
