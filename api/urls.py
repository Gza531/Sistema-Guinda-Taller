from django.urls import path
from .views import EstadoAPIView

urlpatterns = [
    path('estado/', EstadoAPIView.as_view(), name='api-estado'),
]
