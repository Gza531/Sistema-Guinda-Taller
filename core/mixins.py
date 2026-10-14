from rest_framework import status
from rest_framework.response import Response


class BajaLogicaMixin:
    """
    Reemplaza el DELETE de un ViewSet: en lugar de borrar la fila,
    la da de baja poniendo estado = False (baja lógica, según el RIR).
    El modelo tiene que tener un campo booleano llamado "estado".
    """

    def destroy(self, request, *args, **kwargs):
        objeto = self.get_object()
        objeto.estado = False
        objeto.save(update_fields=["estado"])
        return Response(self.get_serializer(objeto).data, status=status.HTTP_200_OK)

    def get_queryset(self):
        qs = super().get_queryset()
        estado = self.request.query_params.get("estado")
        if estado in ("true", "1"):
            qs = qs.filter(estado=True)
        elif estado in ("false", "0"):
            qs = qs.filter(estado=False)
        return qs