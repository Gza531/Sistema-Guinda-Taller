from rest_framework import serializers


class VentasPorTipoSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)


class VentasHoySerializer(serializers.Serializer):
    fecha = serializers.DateField()
    cantidad = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    presencial = VentasPorTipoSerializer()
    online = VentasPorTipoSerializer()
    anuladas = serializers.IntegerField()


class StockBajoMinimoSerializer(serializers.Serializer):
    id_producto = serializers.IntegerField()
    producto = serializers.CharField()
    ubicacion = serializers.CharField()
    cantidad_actual = serializers.IntegerField()
    stock_minimo = serializers.IntegerField()
    faltante = serializers.IntegerField()


class CajaAbiertaSerializer(serializers.Serializer):
    id_caja = serializers.IntegerField()
    caja = serializers.CharField()
    tipo_caja = serializers.CharField()
    id_sesion = serializers.IntegerField()
    abierta_desde = serializers.DateTimeField()
    abierta_por = serializers.CharField(allow_null=True)
    efectivo_esperado = serializers.DecimalField(max_digits=14, decimal_places=2)

class CantidadPorEstadoSerializer(serializers.Serializer):
    estado = serializers.CharField()
    nombre = serializers.CharField()
    cantidad = serializers.IntegerField()


class ResumenPorEstadoSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    por_estado = CantidadPorEstadoSerializer(many=True)

class DashboardSerializer(serializers.Serializer):
    ventas_hoy = VentasHoySerializer()
    stock_bajo_minimo = StockBajoMinimoSerializer(many=True)
    cajas_abiertas = CajaAbiertaSerializer(many=True)
    pedidos_pendientes = ResumenPorEstadoSerializer()
    envios_en_curso = ResumenPorEstadoSerializer()