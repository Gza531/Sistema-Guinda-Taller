"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include

from core.views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),

    # Todas las rutas de la API REST quedan agrupadas bajo el prefijo /api/.
    # A medida que agreguen mas endpoints (por app), inclúyanlos aca mismo,
    # por ejemplo: path('api/clientes/', include('clientes.urls')).
    path('api/', include('api.urls')),
]
