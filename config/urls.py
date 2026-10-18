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
    
    path('api/stock/', include('stock.urls')),
    path('api/cajas/', include('cajas.urls')),  
    path('api/clientes/', include('clientes.urls')),
    path('api/ventas/', include('ventas.urls')),
    path('api/proveedores/', include('proveedores.urls')),
    path('api/compras/', include('compras.urls')),
    path('api/pedidos/', include('pedidos.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    path('api/', include('api.urls')),
]
