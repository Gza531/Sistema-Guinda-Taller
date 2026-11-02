
import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from clientes.models import Cliente


logger = logging.getLogger(__name__)

MENSAJE_GENERICO = (
    "Si el email está registrado, te enviamos un enlace "
    "para restablecer tu contraseña."
)

MENSAJE_TOKEN_INVALIDO = "El enlace es inválido o venció."


class SolicitarRecuperacionSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class ConfirmarRecuperacionSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, datos):
        try:
            usuario_id = int(
                force_str(urlsafe_base64_decode(datos["uid"]))
            )
        except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
            raise serializers.ValidationError({
                "token": MENSAJE_TOKEN_INVALIDO
            })

        cliente = Cliente.objects.select_related("usuario").filter(
            usuario_id=usuario_id,
            estado=True,
            usuario__is_active=True,
        ).first()

        if cliente is None:
            raise serializers.ValidationError({
                "token": MENSAJE_TOKEN_INVALIDO
            })

        usuario = cliente.usuario

        if not default_token_generator.check_token(usuario, datos["token"]):
            raise serializers.ValidationError({
                "token": MENSAJE_TOKEN_INVALIDO
            })

        try:
            validate_password(datos["password"], user=usuario)
        except DjangoValidationError as error:
            raise serializers.ValidationError({
                "password": error.messages
            })

        datos["usuario"] = usuario
        return datos


class RecuperarPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recuperar_password"

    def post(self, request):
        serializer = SolicitarRecuperacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        clientes = Cliente.objects.select_related("usuario").filter(
            usuario__email__iexact=email,
            usuario__is_active=True,
            estado=True,
        )

        for cliente in clientes:
            usuario = cliente.usuario

            uid = urlsafe_base64_encode(force_bytes(usuario.pk))
            token = default_token_generator.make_token(usuario)

            frontend_url = settings.FRONTEND_URL.rstrip("/")
            enlace = f"{frontend_url}/restablecer/{uid}/{token}"

            asunto = "Recuperar contraseña - Guinda Perfumería"
            mensaje = (
                "Recibimos una solicitud para restablecer tu contraseña.\n\n"
                f"Usá este enlace:\n{enlace}\n\n"
                "Si no solicitaste el cambio, ignorá este correo."
            )

            try:
                send_mail(
                    asunto,
                    mensaje,
                    settings.DEFAULT_FROM_EMAIL,
                    [usuario.email],
                    fail_silently=False,
                )
            except Exception:
                logger.exception(
                    "No se pudo enviar un correo de recuperación."
                )

        return Response({"mensaje": MENSAJE_GENERICO})


class ConfirmarRecuperacionAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "confirmar_password"

    def post(self, request):
        serializer = ConfirmarRecuperacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = serializer.validated_data["usuario"]
        usuario.set_password(serializer.validated_data["password"])
        usuario.save(update_fields=["password"])

        return Response({
            "mensaje": "La contraseña se actualizó correctamente."
        })
