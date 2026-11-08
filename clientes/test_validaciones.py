from django.test import TestCase
from rest_framework.test import APIClient

from clientes.validaciones import validar_nombre_persona
from clientes.serializers import ClienteSerializer, EditarMiPerfilSerializer


class ValidacionNombresTests(TestCase):

    def setUp(self):
        self.api = APIClient()

    def datos_registro(self):
        return {
            "username": "usuario_prueba",
            "password": "ClaveSegura#2026!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "email": "usuario_prueba@example.com",
        }

    def test_acepta_nombres_validos(self):
        casos = [
            ("María José", "María José"),
            ("O'Connor", "O'Connor"),
            ("Pérez-Gómez", "Pérez-Gómez"),
            ("  María   José  ", "María José"),
            ("Jose\u0301", "José"),
        ]

        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                self.assertEqual(
                    validar_nombre_persona(entrada, "nombre"),
                    esperado,
                )

    def test_registro_rechaza_nombre_con_numeros(self):
        datos = self.datos_registro()
        datos["nombre"] = "Juan123"

        respuesta = self.api.post("/api/registro/", datos, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("nombre", respuesta.data)

    def test_registro_rechaza_apellido_con_numeros(self):
        datos = self.datos_registro()
        datos["apellido"] = "Pérez45"

        respuesta = self.api.post("/api/registro/", datos, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("apellido", respuesta.data)

    def test_registro_acepta_nombre_valido(self):
        respuesta = self.api.post(
            "/api/registro/",
            self.datos_registro(),
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)

    def test_mi_perfil_rechaza_numeros(self):
        serializer = EditarMiPerfilSerializer(
            data={"nombre": "Juan123"},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("nombre", serializer.errors)

    def test_cliente_serializer_rechaza_numeros(self):
        serializer = ClienteSerializer(
            data={"apellido": "Pérez45"},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("apellido", serializer.errors)
