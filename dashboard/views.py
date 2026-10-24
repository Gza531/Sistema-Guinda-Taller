from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import PermisoPorAccion
from . import services
from .serializers import DashboardSerializer


class DashboardAPIView(APIView):
    permission_classes = [PermisoPorAccion]
    permiso = "ver_dashboard"

    def get(self, request):
        datos = services.resumen()
        return Response(DashboardSerializer(datos).data)