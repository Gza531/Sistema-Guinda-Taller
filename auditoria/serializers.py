import json

from rest_framework import serializers

from .models import Auditoria


class AuditoriaSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)
    accion_texto = serializers.CharField(source="get_accion_display", read_only=True)
    # En la base son texto JSON; acá se devuelven como objetos para que el front los recorra
    datos_previos = serializers.SerializerMethodField()
    datos_nuevos = serializers.SerializerMethodField()

    class Meta:
        model = Auditoria
        fields = ["id_auditoria", "fecha_hora", "usuario", "usuario_username", "accion",
                  "accion_texto", "tabla_afectada", "id_registro_afectado",
                  "datos_previos", "datos_nuevos"]
        read_only_fields = fields

    @staticmethod
    def _objeto(texto):
        if not texto:
            return None
        try:
            return json.loads(texto)
        except ValueError:
            return texto

    def get_datos_previos(self, registro):
        return self._objeto(registro.datos_previos)

    def get_datos_nuevos(self, registro):
        return self._objeto(registro.datos_nuevos)
