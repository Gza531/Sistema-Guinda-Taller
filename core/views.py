from django.shortcuts import render
from django.utils import timezone


def home(request):
    """
    Vista de bienvenida. Sirve para confirmar que el stack completo
    (Django + Postgres, corriendo en contenedores Docker) esta funcionando.
    Reemplacen esta vista por las de su propio proyecto.
    """
    contexto = {
        'hora_actual': timezone.now(),
    }
    return render(request, 'core/home.html', contexto)
