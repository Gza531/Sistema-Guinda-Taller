"""
Carga un set COMPLETO de datos de prueba para recorrer todo el sistema.

Uso (con un superusuario ya creado):
    docker compose exec web python manage.py cargar_escenarios

Primero ejecuta cargar_datos_prueba (catálogo, stock, clientes, proveedores, cajas,
compras) y después agrega, siempre a través de los servicios del sistema (así el
stock, la caja y los envíos quedan consistentes):

- Empleados con cada rol (y uno dado de baja).
- Clientes con usuario para la tienda web.
- Promociones vigentes, vencidas, futuras e inactivas.
- Un traslado de stock y productos con stock bajo.
- Una sesión de caja cerrada (con diferencia) y otra abierta, con ventas presenciales,
  pagos combinados, movimientos manuales y una venta anulada.
- Ventas online con retiro y con envíos en todos los estados.
- Una venta web "pagada por Mercado Pago" (simulada).
- Pedidos en cada estado (uno Listo para probar /entregar/).
- Compras pendiente, recibida y pagada, y anulada.

Todo se hace en una sola transacción: si algo falla, no queda nada a medias.
Solo se puede correr una vez por base (si ya hay ventas, no hace nada).
Contraseña de todos los usuarios de prueba: Guinda.2026!
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cajas import services as cajas_services
from cajas.models import AperturaCierreCaja, Caja, MetodoPago, MovimientoCaja
from catalogo.models import Producto
from clientes import services as clientes_services
from clientes.models import Cliente
from compras import services as compras_services
from compras.models import Compra
from core.permissions import DUENA, ENCARGADA, RESP_ONLINE, RESP_STOCK, VENDEDOR
from envios import services as envios_services
from envios.models import Envio
from pedidos import services as pedidos_services
from pedidos.models import Pedido
from promociones import services as promociones_services
from promociones.models import Promocion
from proveedores.models import Proveedor
from seguridad import services as seguridad_services
from stock import services as stock_services
from stock.models import Stock
from ventas import services as ventas_services
from ventas.models import Venta

PASSWORD = "Guinda.2026!"

EMPLEADOS = [
    # usuario, nombre, apellido, dni, roles
    ("duena", "Graciela", "Guinda", "20111111", [DUENA]),
    ("encargada", "Paula", "Rivas", "27222222", [ENCARGADA]),
    ("vendedor", "Tomás", "Herrera", "38333333", [VENDEDOR]),
    ("stock", "Ramiro", "Cruz", "36444444", [RESP_STOCK]),
    ("online", "Lucía", "Mendoza", "39555555", [RESP_ONLINE]),
    ("multirol", "Diego", "Sosa", "37666666", [VENDEDOR, RESP_STOCK]),
    ("exempleado", "Marcos", "Vidal", "33777777", [VENDEDOR]),  # se da de baja
]

CLIENTES_WEB = [
    # usuario, nombre, apellido, dni, email, teléfono, dirección
    # «ana» se vincula con la clienta Ana Pérez que ya existe (mismo DNI)
    ("ana", "Ana", "Pérez", "30111222", "ana.perez@mail.com", "3874111222", "Belgrano 123, Salta"),
    ("carla", "Carla", "Benítez", "41222333", "carla.benitez@mail.com", "3874222333", "Caseros 850, Salta"),
    ("martin", "Martín", "López", "42333444", "martin.lopez@mail.com", None, None),  # sin dirección
]


def _producto(nombre):
    return Producto.objects.get(nombre=nombre)


def _metodo(nombre):
    return MetodoPago.objects.get(nombre=nombre)


def _item(nombre, cantidad):
    return {"producto": _producto(nombre), "cantidad": cantidad}


def _pago(nombre_metodo, monto):
    return {"metodo_pago": _metodo(nombre_metodo), "monto": Decimal(monto)}


def _total_presencial(items):
    """Total con las promociones vigentes (para armar pagos exactos)."""
    lineas = ventas_services._armar_lineas(ventas_services._agrupar(items))
    return sum((linea["subtotal"] for linea in lineas), Decimal("0.00"))


class Command(BaseCommand):
    help = "Carga un set completo de datos de prueba (empleados, ventas, caja, pedidos, envíos...)."

    def handle(self, *args, **options):
        Usuario = get_user_model()
        admin = Usuario.objects.filter(is_superuser=True).order_by("pk").first()
        if admin is None:
            raise CommandError("Primero creá un superusuario: python manage.py createsuperuser")

        if Venta.objects.exists():
            self.stdout.write(self.style.WARNING(
                "Esta base ya tiene ventas: no se cargan escenarios para no duplicar datos."
            ))
            return

        call_command("cargar_datos_prueba", stdout=self.stdout)

        with transaction.atomic():
            usuarios = self._empleados(admin)
            clientes = self._clientes_web()
            self._promociones()
            self._stock(usuarios)
            self._caja_y_ventas_presenciales(usuarios)
            self._ventas_online(usuarios, clientes)
            self._pedidos(usuarios, clientes)
            self._compras(usuarios)

        self._resumen()

    # ------------------------------------------------------------------ empleados

    def _empleados(self, admin):
        usuarios = {}
        for username, nombre, apellido, dni, roles in EMPLEADOS:
            empleado = seguridad_services.crear_empleado(
                actor=admin, username=username, password=PASSWORD, roles=roles,
                nombre=nombre, apellido=apellido, dni=dni,
                email=f"{username}@guinda.test",
            )
            usuarios[username] = empleado.usuario

        exempleado = usuarios["exempleado"].empleado
        seguridad_services.dar_de_baja(actor=admin, empleado=exempleado)
        return usuarios

    # ------------------------------------------------------------------ clientes

    def _clientes_web(self):
        clientes = {}
        for username, nombre, apellido, dni, email, telefono, direccion in CLIENTES_WEB:
            cliente, _ = clientes_services.registrar_cliente(
                username=username, password=PASSWORD, nombre=nombre, apellido=apellido,
                email=email, telefono=telefono, direccion=direccion,
                tipo_documento="DNI", nro_documento=dni,
            )
            clientes[username] = cliente

        # Una clienta dada de baja (para probar filtros y que no pueda comprar)
        sol = Cliente.objects.get(nro_documento="35555666")
        sol.estado = False
        sol.save(update_fields=["estado"])

        clientes["luis"] = Cliente.objects.get(nro_documento="28333444")
        return clientes

    # ------------------------------------------------------------------ promociones

    def _promociones(self):
        hoy = date.today()
        T = Promocion.TipoDescuento
        promociones_services.crear_promocion(
            nombre="Semana de las fragancias", descripcion="20% en fragancias seleccionadas",
            tipo_descuento=T.PORCENTAJE, valor_descuento=Decimal("20"),
            fecha_inicio=hoy - timedelta(days=3), fecha_fin=hoy + timedelta(days=10),
            productos=[_producto("Good Girl EDP"), _producto("212 VIP Men")],
        )
        promociones_services.crear_promocion(
            nombre="Máscara con descuento", descripcion="$2.000 menos en máscaras",
            tipo_descuento=T.MONTO_FIJO, valor_descuento=Decimal("2000"),
            fecha_inicio=hoy, fecha_fin=hoy + timedelta(days=30),
            productos=[_producto("Máscara Lash Sensational")],
        )
        promociones_services.crear_promocion(
            nombre="Día del padre (vencida)", descripcion="Ya terminó: no debe aplicarse",
            tipo_descuento=T.PORCENTAJE, valor_descuento=Decimal("15"),
            fecha_inicio=hoy - timedelta(days=40), fecha_fin=hoy - timedelta(days=30),
            productos=[_producto("Sauvage EDT")],
        )
        promociones_services.crear_promocion(
            nombre="Navidad (futura)", descripcion="Todavía no empezó",
            tipo_descuento=T.PORCENTAJE, valor_descuento=Decimal("10"),
            fecha_inicio=hoy + timedelta(days=30), fecha_fin=hoy + timedelta(days=60),
            productos=[_producto("Desodorante Kaiak")],
        )
        inactiva = promociones_services.crear_promocion(
            nombre="Promo dada de baja", descripcion="Vigente por fechas, pero inactiva",
            tipo_descuento=T.PORCENTAJE, valor_descuento=Decimal("30"),
            fecha_inicio=hoy - timedelta(days=1), fecha_fin=hoy + timedelta(days=5),
            productos=[_producto("Base True Match")],
        )
        inactiva.estado = False
        inactiva.save(update_fields=["estado"])

    # ------------------------------------------------------------------ stock

    def _stock(self, usuarios):
        # El salón no tenía Desodorante Ekos: se traslada desde el depósito.
        stock_services.registrar_reposicion(
            producto=_producto("Desodorante Ekos"), origen=Stock.Ubicaciones.DEPOSITO,
            cantidad=12, usuario=usuarios["stock"], motivo="Reposición del salón",
        )
        # Ingreso manual (por ejemplo, mercadería encontrada en un recuento)
        stock_services.registrar_entrada(
            producto=_producto("Base True Match"), ubicacion=Stock.Ubicaciones.DEPOSITO,
            cantidad=4, usuario=usuarios["stock"], motivo="Ajuste por recuento",
        )
        # Chanel N°5 queda con stock bajo (1 en el salón, mínimo 2; 0 en depósito).

    # ------------------------------------------------------------------ caja y ventas presenciales

    def _caja_y_ventas_presenciales(self, usuarios):
        salon = Caja.objects.get(nombre="Caja salón")
        vendedor, encargada = usuarios["vendedor"], usuarios["encargada"]

        # ---- Sesión 1: se abre, se vende y se cierra con un faltante de $500
        sesion1 = cajas_services.abrir_caja(
            caja=salon, usuario=vendedor, monto_inicial=Decimal("20000"),
            observaciones="Turno mañana",
        )
        items = [_item("1 Million EDT", 1)]
        ventas_services.registrar_venta_presencial(
            usuario=vendedor, caja=salon, items=items,
            pagos=[_pago("Efectivo", _total_presencial(items))],
        )
        items = [_item("Labial SuperStay Matte Ink", 2), _item("Desodorante Kaiak", 1)]
        ventas_services.registrar_venta_presencial(
            usuario=vendedor, caja=salon, items=items, cliente=Cliente.objects.get(nro_documento="30111222"),
            pagos=[_pago("Débito", _total_presencial(items))],
        )
        esperado = cajas_services.resumen_sesion(sesion1)["efectivo_esperado"]
        cajas_services.cerrar_caja(
            sesion=sesion1, monto_final=esperado - Decimal("500"),
            observaciones="Faltante de $500 (error de vuelto)",
        )

        # ---- Sesión 2: queda abierta para seguir probando
        cajas_services.abrir_caja(
            caja=salon, usuario=vendedor, monto_inicial=Decimal("15000"), observaciones="Turno tarde",
        )
        # Con promoción vigente (Good Girl -20%) y pago combinado
        items = [_item("Good Girl EDP", 1), _item("Máscara Lash Sensational", 2)]
        total = _total_presencial(items)
        ventas_services.registrar_venta_presencial(
            usuario=vendedor, caja=salon, items=items, cliente=Cliente.objects.get(nro_documento="28333444"),
            pagos=[_pago("Efectivo", "50000"), _pago("Crédito", total - Decimal("50000"))],
        )
        items = [_item("Sauvage EDT", 1)]  # promoción vencida: precio de lista
        ventas_services.registrar_venta_presencial(
            usuario=vendedor, caja=salon, items=items,
            pagos=[_pago("Transferencia", _total_presencial(items))],
        )
        # Venta que después se anula (vuelve el stock y sale el dinero)
        items = [_item("Desodorante Ekos", 2)]
        anulable = ventas_services.registrar_venta_presencial(
            usuario=vendedor, caja=salon, items=items,
            pagos=[_pago("Efectivo", _total_presencial(items))],
        )
        ventas_services.anular_venta(venta=anulable, usuario=encargada, motivo="Error de carga")

        # Movimientos manuales (los hace la Encargada)
        cajas_services.registrar_movimiento_caja(
            caja=salon, tipo_movimiento=MovimientoCaja.TipoMovimiento.EGRESO,
            monto=Decimal("3500"), metodo_pago=_metodo("Efectivo"),
            concepto="Compra de artículos de limpieza",
        )
        cajas_services.registrar_movimiento_caja(
            caja=salon, tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO,
            monto=Decimal("10000"), metodo_pago=_metodo("Efectivo"),
            concepto="Refuerzo de cambio",
        )

    # ------------------------------------------------------------------ ventas online y envíos

    def _ventas_online(self, usuarios, clientes):
        online = usuarios["online"]
        E = Envio.EstadoEnvio

        def venta(cliente, items, metodo, entrega="ENVIO", costo="3500", direccion=None, obs=None):
            costo = Decimal(costo) if entrega == "ENVIO" else None
            total = _total_presencial(items) + (costo or Decimal("0"))
            return ventas_services.registrar_venta_online(
                usuario=online, cliente=cliente, items=items, pagos=[_pago(metodo, total)],
                entrega=entrega, costo_envio=costo, direccion_entrega=direccion, observaciones=obs,
            )

        # Retiro en el local
        venta(clientes["luis"], [_item("Base True Match", 1)], "Transferencia", entrega="RETIRO",
              obs="Pedido por WhatsApp, retira en el local")

        # Envíos en distintos estados
        def avanzar(v, *estados_destino, empresa="Correo Argentino", codigo=None):
            envio = Envio.objects.get(venta=v)
            for estado in estados_destino:
                envio = envios_services.cambiar_estado(
                    envio=envio, estado=estado, empresa_transporte=empresa, codigo_seguimiento=codigo,
                )
            return envio

        venta(clientes["carla"], [_item("Desodorante Kaiak", 2)], "Mercado Pago")                    # PENDIENTE
        v = venta(clientes["carla"], [_item("Labial SuperStay Matte Ink", 1)], "Transferencia")
        avanzar(v, E.PREPARADO)
        v = venta(clientes["ana"], [_item("212 VIP Men", 1)], "Crédito")
        avanzar(v, E.PREPARADO, E.DESPACHADO, codigo="CA123456789AR")
        v = venta(clientes["luis"], [_item("Máscara Lash Sensational", 3)], "Débito", direccion="Mitre 456, Salta")
        avanzar(v, E.PREPARADO, E.DESPACHADO, E.EN_TRANSITO, E.ENTREGADO, codigo="CA987654321AR")
        v = venta(clientes["ana"], [_item("Desodorante Ekos", 1)], "Transferencia")
        avanzar(v, E.PREPARADO, E.DESPACHADO, E.DEMORADO, empresa="Andreani", codigo="AND-55501")
        v = venta(clientes["carla"], [_item("Base True Match", 1)], "Débito")
        avanzar(v, E.PREPARADO, E.DESPACHADO, E.EN_TRANSITO, E.DEVUELTO, codigo="CA555000111AR")

        # Venta "de la tienda web" como la registra el webhook de Mercado Pago (simulada:
        # el pago no existe en Mercado Pago, así que anularla dará error de devolución).
        items = [_item("Miss Dior EDP", 1)]
        total = _total_presencial(items) + Decimal("3500")
        ventas_services.registrar_venta_online(
            usuario=clientes["carla"].usuario, cliente=clientes["carla"], items=items,
            pagos=[_pago("Mercado Pago", total)], entrega="ENVIO", costo_envio=Decimal("3500"),
            observaciones="Tienda web · pago Mercado Pago SIMULADO (no anular)",
            mp_payment_id="SIMULADO-0001",
        )

    # ------------------------------------------------------------------ pedidos

    def _pedidos(self, usuarios, clientes):
        P = Pedido.EstadoPedido
        vendedor, online = usuarios["vendedor"], usuarios["online"]

        def pedido(cliente, canal, items, estados=(), usuario=vendedor, obs=None):
            p = pedidos_services.crear_pedido(
                cliente=cliente, canal=canal, items=items, usuario=usuario, observaciones=obs,
            )
            for estado in estados:
                p = pedidos_services.cambiar_estado(pedido=p, estado=estado)
            return p

        pedido(clientes["ana"], "WHATSAPP", [_item("Chanel N°5 EDP", 1)], obs="Consulta por Chanel N°5")
        pedido(clientes["luis"], "INSTAGRAM", [_item("Good Girl EDP", 1)], [P.RESERVADO])
        pedido(clientes["carla"], "WHATSAPP", [_item("Chanel N°5 EDP", 2)], [P.EN_ESPERA_STOCK],
               obs="Esperando reposición del proveedor")
        pedido(clientes["martin"], "WEB", [_item("1 Million EDT", 1), _item("Desodorante Kaiak", 1)],
               [P.RESERVADO, P.LISTO], usuario=online, obs="Listo: probar /entregar/")
        listo = pedido(clientes["ana"], "PRESENCIAL", [_item("Labial SuperStay Matte Ink", 2)],
                       [P.RESERVADO, P.LISTO])
        total = sum(d.precio_referencia * d.cantidad for d in listo.detallepedido_set.all())
        pedidos_services.entregar_pedido(
            pedido=listo, usuario=online, pagos=[_pago("Transferencia", total)], entrega="RETIRO",
        )
        cancelado = pedido(clientes["luis"], "WHATSAPP", [_item("Sauvage EDT", 1)])
        pedidos_services.cancelar_pedido(pedido=cancelado, motivo="El cliente desistió")

    # ------------------------------------------------------------------ compras

    def _compras(self, usuarios):
        salon = Caja.objects.get(nombre="Caja salón")
        recibida = Compra.objects.filter(numero_factura="A-0001-00001234").first()
        if recibida is not None:
            compras_services.pagar_compra(compra=recibida, caja=salon, metodo_pago=_metodo("Transferencia"))

        natura = Proveedor.objects.get(razon_social="Natura Distribución Salta")
        a_anular = compras_services.crear_compra(
            proveedor=natura, usuario=usuarios["duena"], observaciones="Cargada por error",
            detalles=[{"producto": _producto("Desodorante Kaiak"), "cantidad": 10, "precio_unitario": Decimal("5800")}],
        )
        compras_services.anular_compra(compra=a_anular)

    # ------------------------------------------------------------------ resumen

    def _resumen(self):
        self.stdout.write(self.style.SUCCESS("\nEscenarios cargados."))
        self.stdout.write(
            f"  Ventas: {Venta.objects.count()} "
            f"({Venta.objects.filter(estado='ANULADA').count()} anulada) · "
            f"Envíos: {Envio.objects.count()} · Pedidos: {Pedido.objects.count()} · "
            f"Promociones: {Promocion.objects.count()} · Compras: {Compra.objects.count()} · "
            f"Sesiones de caja: {AperturaCierreCaja.objects.count()}"
        )
        self.stdout.write(f"\nUsuarios de prueba (contraseña de todos: {PASSWORD})")
        for username, nombre, apellido, _, roles in EMPLEADOS:
            extra = "  ← dado de baja: no puede ingresar" if username == "exempleado" else ""
            self.stdout.write(f"  {username:<11} {', '.join(roles)}{extra}")
        for username, nombre, apellido, *_ in CLIENTES_WEB:
            self.stdout.write(f"  {username:<11} Cliente ({nombre} {apellido})")
