
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from clientes.models import Cliente
from seguridad.models import Empleado, Usuario


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://localhost:5173",
)
class RecuperacionPasswordTests(TestCase):

    SOLICITAR = "/api/recuperar-password/"
    CONFIRMAR = "/api/recuperar-password/confirmar/"

    def setUp(self):
        cache.clear()

        self.usuario = Usuario.objects.create_user(
            username="cliente_recuperacion",
            email="cliente.prueba@example.com",
            password="ClaveAnterior!8294",
        )

        self.cliente = Cliente.objects.create(
            nombre="Cliente",
            apellido="Prueba",
            email=self.usuario.email,
            usuario=self.usuario,
            estado=True,
        )

        self.uid = urlsafe_base64_encode(
            force_bytes(self.usuario.pk)
        )

    def solicitar(self, email):
        return self.client.post(
            self.SOLICITAR,
            {"email": email},
            content_type="application/json",
        )

    def confirmar(self, token, password="NuevaClaveSegura!8472"):
        return self.client.post(
            self.CONFIRMAR,
            {
                "uid": self.uid,
                "token": token,
                "password": password,
            },
            content_type="application/json",
        )

    def test_cliente_activo_recibe_enlace(self):
        respuesta = self.solicitar(self.usuario.email)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        correo = mail.outbox[0]

        self.assertEqual(correo.to, [self.usuario.email])
        self.assertIn(
            f"http://localhost:5173/restablecer/{self.uid}/",
            correo.body,
        )

    def test_email_inexistente_no_revela_cuenta(self):
        existente = self.solicitar(self.usuario.email)
        inexistente = self.solicitar("no-existe@example.com")

        self.assertEqual(existente.status_code, 200)
        self.assertEqual(inexistente.status_code, 200)
        self.assertEqual(existente.json(), inexistente.json())

        # Solo se generó un correo: el del cliente existente.
        self.assertEqual(len(mail.outbox), 1)

    def test_cambio_correcto_invalida_enlace(self):
        token = default_token_generator.make_token(self.usuario)

        respuesta = self.confirmar(token)

        self.assertEqual(respuesta.status_code, 200)

        self.usuario.refresh_from_db()

        self.assertTrue(
            self.usuario.check_password("NuevaClaveSegura!8472")
        )
        self.assertFalse(
            self.usuario.check_password("ClaveAnterior!8294")
        )

        # El mismo enlace no puede utilizarse nuevamente.
        segunda = self.confirmar(token)

        self.assertEqual(segunda.status_code, 400)

    def test_token_invalido_es_rechazado(self):
        respuesta = self.confirmar("token-invalido")

        self.assertEqual(respuesta.status_code, 400)

        self.usuario.refresh_from_db()
        self.assertTrue(
            self.usuario.check_password("ClaveAnterior!8294")
        )

    @override_settings(PASSWORD_RESET_TIMEOUT=60)
    def test_token_vencido_es_rechazado(self):
        hace_cinco_minutos = datetime.now() - timedelta(
            minutes=5
        )

        with patch.object(
            default_token_generator,
            "_now",
            return_value=hace_cinco_minutos,
        ):
            token = default_token_generator.make_token(
                self.usuario
            )

        respuesta = self.confirmar(token)

        self.assertEqual(respuesta.status_code, 400)

    def test_usuario_inactivo_no_puede_recuperar(self):
        token = default_token_generator.make_token(self.usuario)

        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])

        respuesta = self.solicitar(self.usuario.email)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.confirmar(token).status_code, 400)

    def test_cliente_dado_de_baja_no_puede_recuperar(self):
        token = default_token_generator.make_token(self.usuario)

        self.cliente.estado = False
        self.cliente.save(update_fields=["estado"])

        respuesta = self.solicitar(self.usuario.email)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.confirmar(token).status_code, 400)

    def test_empleado_sin_cliente_no_puede_recuperar(self):
        empleado_usuario = Usuario.objects.create_user(
            username="empleado_prueba",
            email="empleado@example.com",
            password="ClaveEmpleado!8294",
        )

        Empleado.objects.create(
            usuario=empleado_usuario,
            nombre="Empleado",
            apellido="Prueba",
            estado=True,
        )

        respuesta = self.solicitar(empleado_usuario.email)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

        token = default_token_generator.make_token(
            empleado_usuario
        )
        uid = urlsafe_base64_encode(
            force_bytes(empleado_usuario.pk)
        )

        confirmacion = self.client.post(
            self.CONFIRMAR,
            {
                "uid": uid,
                "token": token,
                "password": "OtraClaveSegura!8472",
            },
            content_type="application/json",
        )

        self.assertEqual(confirmacion.status_code, 400)

    def test_empleado_con_cliente_no_recibe_enlace(self):
        Empleado.objects.create(
            usuario=self.usuario,
            nombre="Empleado",
            apellido="Con Cliente",
            estado=True,
        )

        respuesta = self.solicitar(self.usuario.email)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

        # No debe revelar que la cuenta pertenece a un empleado.
        inexistente = self.solicitar("no-existe@example.com")

        self.assertEqual(respuesta.json(), inexistente.json())

    def test_superusuario_con_cliente_no_puede_recuperar(self):
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=["is_superuser"])

        token = default_token_generator.make_token(self.usuario)

        respuesta = self.solicitar(self.usuario.email)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

        confirmacion = self.confirmar(token)

        self.assertEqual(confirmacion.status_code, 400)

        self.usuario.refresh_from_db()
        self.assertTrue(
            self.usuario.check_password("ClaveAnterior!8294")
        )

    def test_token_anterior_a_alta_empleado_es_rechazado(self):
        # El token se genera cuando todavía es un cliente normal.
        token = default_token_generator.make_token(self.usuario)

        # Posteriormente, el usuario pasa a tener ficha de empleado.
        Empleado.objects.create(
            usuario=self.usuario,
            nombre="Nuevo",
            apellido="Empleado",
            estado=True,
        )

        respuesta = self.confirmar(token)

        self.assertEqual(respuesta.status_code, 400)

        self.usuario.refresh_from_db()

        self.assertTrue(
            self.usuario.check_password("ClaveAnterior!8294")
        )

    def test_password_insegura_es_rechazada(self):
        token = default_token_generator.make_token(self.usuario)

        respuesta = self.confirmar(token, "12345678")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("password", respuesta.json())

    def test_limite_de_solicitudes(self):
        for _ in range(5):
            respuesta = self.solicitar("no-existe@example.com")
            self.assertEqual(respuesta.status_code, 200)

        respuesta = self.solicitar("no-existe@example.com")

        self.assertEqual(respuesta.status_code, 429)
