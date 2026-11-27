"""
Datos para la demo con los productos que ya están cargados.

    docker compose exec web python manage.py cargar_demo
    (modo servidor: docker compose -f compose.servidor.yaml exec web python manage.py cargar_demo)

Usa las marcas, categorías y productos que hay en la base (hacen falta al menos 6
productos activos) y agrega:

- Empleados (uno por rol), métodos de pago, cajas, proveedores y clientes (con y
  sin cuenta en la tienda). Lo que ya existe no se duplica.
- Qué provee cada proveedor y compras (recibidas, pagada, pendiente y anulada).
- Traslados al salón, mínimos de stock y un ajuste por recuento.
- Promociones (vigentes, vencida y futura).
- Dos sesiones de la caja del salón con ventas presenciales, pago combinado,
  una venta anulada y movimientos manuales.
- Ventas online con envío por zona, envíos en cada estado y pedidos en cada estado.

Todo pasa por los servicios del sistema, así el stock, la caja, los envíos y la
auditoría quedan consistentes. Corre en una sola transacción: si algo falla, no
queda nada a medias. Se carga una sola vez (si la demo ya está, no hace nada).

Requiere un superusuario (createsuperuser). Contraseña de todas las cuentas de la
demo: Guinda.2026!
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
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
from pagos.tarifas import tarifa_envio
from pedidos import services as pedidos_services
from pedidos.models import Pedido
from promociones import services as promociones_services
from promociones.models import Promocion
from proveedores.models import Proveedor, ProveedorXProducto
from seguridad import services as seguridad_services
from seguridad.models import Empleado
from stock import services as stock_services
from stock.models import Stock
from ventas import services as ventas_services
from ventas.models import Venta

PASSWORD = "Guinda.2026!"
MINIMO_PRODUCTOS = 6
FACTURA_DEMO = "A 0003-00004521"   # si ya existe esta compra, la demo está cargada

EMPLEADOS = [
    # usuario, nombre, apellido, dni, teléfono, roles
    ("vguzman", "Valeria", "Guzmán", "28456123", "387 512-0011", [DUENA]),
    ("lmamani", "Lorena", "Mamaní", "31207845", "387 512-0022", [ENCARGADA]),
    ("fcruz", "Facundo", "Cruz", "38654210", "387 512-0033", [VENDEDOR]),
    ("mtolaba", "Micaela", "Tolaba", "40112987", "387 512-0044", [RESP_STOCK]),
    ("jarias", "Julián", "Arias", "39870456", "387 512-0055", [RESP_ONLINE]),
]

# nombre, ¿lo acepta la caja online?
METODOS_PAGO = [("Transferencia", True), ("Tarjeta de débito", False), ("Tarjeta de crédito", False)]

CAJAS = [("Caja salón", Caja.TipoCaja.PRESENCIAL, "Mostrador del salón"),
         ("Caja online", Caja.TipoCaja.ONLINE, "Cobros de la tienda web, ventas online y pedidos")]

PROVEEDORES = [
    # razón social, CUIT, teléfono, email, dirección, observaciones
    ("Distribuidora Norte Fragancias S.R.L.", "30-71584236-9", "387 421-5530",
     "ventas@nortefragancias.com.ar", "Av. Tavella 1450, Salta", "Entrega a 7 días. Pedido mínimo 6 unidades."),
    ("Cosmética del Valle S.A.", "30-70985412-3", "387 431-2207",
     "pedidos@cosmeticadelvalle.com.ar", "Alvarado 920, Salta", "Pago a 30 días."),
    ("Accesorios del Norte", "20-29845671-3", "387 455-9012",
     "contacto@accesoriosnorte.com.ar", "Florida 340, Salta", "Todavía sin compras."),
]

# Clientes que carga el personal (sin cuenta en la tienda)
# nombre, apellido, tipo doc, documento, teléfono, email, dirección
CLIENTES_LOCAL = [
    ("Sofía", "Benítez", "DNI", "41235678", "387 498-3344", "sofia.benitez@ejemplo.com",
     "Los Ceibos 245, B° Tres Cerritos, Salta"),
    ("Martín", "Rodríguez", "DNI", "37889102", "387 498-7712", "martin.rodriguez@ejemplo.com",
     "Av. Bolivia 3120, Salta"),
    ("Carla", "Zerpa", "CUIL", "27-39456781-4", "387 498-5521", "carla.zerpa@ejemplo.com",
     "Mitre 1180, Salta"),
    ("Luis", "Gómez", "DNI", "28333444", "387 433-3444", None, "Rivadavia 456, Salta"),
]

# Clientes que se registran en la tienda (usuario, nombre, apellido, email, teléfono, dirección, dni)
# «sbenitez» usa el email y el apellido de Sofía Benítez: se vincula con su ficha, no la duplica.
CLIENTES_WEB = [
    ("sbenitez", "Sofía", "Benítez", "sofia.benitez@ejemplo.com", None, None, None),
    ("tquispe", "Tomás", "Quispe", "tomas.quispe@ejemplo.com", "388 412-7788",
     "Belgrano 845, San Salvador de Jujuy, Jujuy", "40998877"),
    ("acortez", "Agustina", "Cortez", "agustina.cortez@ejemplo.com", "387 15-500-6611",
     "Güemes 210, Cafayate, Salta", "42111999"),
    ("nfarias", "Nicolás", "Farías", "nicolas.farias@ejemplo.com", "351 455-2299",
     "Bv. San Juan 1020, Córdoba, Córdoba", "36777123"),
]


def _redondear(valor):
    return Decimal(valor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _metodo(nombre):
    return MetodoPago.objects.get(nombre=nombre)


def _pago(nombre_metodo, monto):
    return {"metodo_pago": _metodo(nombre_metodo), "monto": Decimal(monto)}


def _item(producto, cantidad):
    return {"producto": producto, "cantidad": cantidad}


def _total(items):
    """Total con las promociones vigentes (para armar pagos exactos)."""
    lineas = ventas_services._armar_lineas(ventas_services._agrupar(items))
    return sum((linea["subtotal"] for linea in lineas), Decimal("0.00"))


class Command(BaseCommand):
    help = "Carga datos de demo en todas las secciones con los productos que ya están cargados."

    def handle(self, *args, **options):
        self.admin = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        if self.admin is None:
            raise CommandError("Primero creá un superusuario: python manage.py createsuperuser")

        productos = list(Producto.objects.filter(estado=True).select_related("marca").order_by("pk"))
        if len(productos) < MINIMO_PRODUCTOS:
            raise CommandError(
                f"Hacen falta al menos {MINIMO_PRODUCTOS} productos activos (hay {len(productos)})."
            )

        if Compra.objects.filter(numero_factura=FACTURA_DEMO).exists():
            self.stdout.write(self.style.WARNING("La demo ya está cargada: no se vuelve a cargar."))
            return

        self.P = productos
        with transaction.atomic():
            self._base()
            self._operaciones()
        self._resumen()

    # ================================================================== datos base

    def _base(self):
        for username, nombre, apellido, dni, telefono, roles in EMPLEADOS:
            # Si ya lo cargaron a mano (mismo usuario o mismo DNI), se usa ese
            if not _existe_usuario(username) and not Empleado.objects.filter(dni=dni).exists():
                seguridad_services.crear_empleado(
                    actor=self.admin, username=username, password=PASSWORD, roles=roles,
                    nombre=nombre, apellido=apellido, dni=dni, telefono=telefono,
                    email=f"{_sin_tildes(nombre)}.{_sin_tildes(apellido)}@ejemplo.com".lower(),
                )

        for nombre, online in METODOS_PAGO:
            metodo, _ = MetodoPago.objects.get_or_create(nombre=nombre, defaults={"estado": True})
            if metodo.en_caja_online != online:
                metodo.en_caja_online = online
                metodo.save()

        for nombre, tipo, descripcion in CAJAS:
            if not Caja.objects.filter(tipo_caja=tipo, estado=True).exists():
                Caja.objects.get_or_create(nombre=nombre, defaults={"tipo_caja": tipo, "descripcion": descripcion})

        for razon, cuit, telefono, email, direccion, obs in PROVEEDORES:
            Proveedor.objects.get_or_create(cuit=cuit, defaults={
                "razon_social": razon, "telefono": telefono, "email": email,
                "direccion": direccion, "observaciones": obs,
            })

        for nombre, apellido, tipo, doc, telefono, email, direccion in CLIENTES_LOCAL:
            if not Cliente.objects.filter(nro_documento=doc).exists():
                Cliente.objects.create(
                    nombre=nombre, apellido=apellido, tipo_documento=tipo, nro_documento=doc,
                    telefono=telefono, email=email, direccion=direccion,
                )

        Usuario = get_user_model()
        for username, nombre, apellido, email, telefono, direccion, dni in CLIENTES_WEB:
            if not Usuario.objects.filter(username__iexact=username).exists():
                clientes_services.registrar_cliente(
                    username=username, password=PASSWORD, nombre=nombre, apellido=apellido,
                    email=email, telefono=telefono, direccion=direccion,
                    tipo_documento="DNI" if dni else None, nro_documento=dni,
                )

    # ================================================================== operaciones

    def _operaciones(self):
        u = {username: _usuario_del_empleado(username, dni) for username, _n, _a, dni, *_ in EMPLEADOS}
        self.u = u
        self.salon = Caja.objects.filter(tipo_caja=Caja.TipoCaja.PRESENCIAL, estado=True).order_by("pk").first()

        # La caja del salón abre primero: desde ahí se pagan las compras.
        # Si ya tenía una sesión abierta (la abrieron a mano), se usa esa y no se
        # arma el turno mañana cerrado.
        self.sesion_manana = None
        if not AperturaCierreCaja.objects.filter(caja=self.salon, fecha_cierre__isnull=True).exists():
            self.sesion_manana = cajas_services.abrir_caja(
                caja=self.salon, usuario=u["fcruz"], monto_inicial=Decimal("50000"), observaciones="Turno mañana",
            )

        self._proveedores_y_compras()
        self._stock()
        self._promociones()
        self._ventas_presenciales()
        self._ventas_online()
        self._pedidos()

    # ------------------------------------------------------------------ proveedores y compras

    def _proveedores_y_compras(self):
        norte, valle, _accesorios = (Proveedor.objects.get(cuit=p[1]) for p in PROVEEDORES)

        # Importados a Norte Fragancias, nacionales a Cosmética del Valle
        # (si todos son del mismo origen, se reparten alternados)
        importados = [p for p in self.P if p.origen == Producto.OrigenProducto.IMPORTADO]
        nacionales = [p for p in self.P if p.origen != Producto.OrigenProducto.IMPORTADO]
        if not importados or not nacionales:
            importados, nacionales = self.P[0::2], self.P[1::2]
        self.por_proveedor = {norte: importados, valle: nacionales}

        for proveedor, productos in self.por_proveedor.items():
            sigla = "NF" if proveedor == norte else "CV"
            for i, producto in enumerate(productos, start=1):
                ProveedorXProducto.objects.get_or_create(
                    proveedor=proveedor, producto=producto,
                    defaults={
                        "precio_compra_referencia": _redondear(producto.precio_venta * Decimal("0.6")),
                        "codigo_producto_proveedor": f"{sigla}-{i:03d}",
                    },
                )

        def detalles(productos, factor=1):
            return [{
                "producto": p,
                "cantidad": (24 if p.precio_venta < 50000 else 12) * factor,
                "precio_unitario": _redondear(p.precio_venta * Decimal("0.6")),
            } for p in productos]

        # Dos compras recibidas (cargan el Depósito); la de Norte ya está pagada
        compra_norte = compras_services.crear_compra(
            proveedor=norte, usuario=self.u["vguzman"], numero_factura=FACTURA_DEMO,
            detalles=detalles(importados), observaciones="Reposición mensual",
        )
        compra_valle = compras_services.crear_compra(
            proveedor=valle, usuario=self.u["vguzman"], numero_factura="A 0012-00018877",
            detalles=detalles(nacionales),
        )
        for compra in (compra_norte, compra_valle):
            compras_services.recibir_compra(compra=compra, usuario=self.u["mtolaba"])
        compras_services.pagar_compra(compra=compra_norte, caja=self.salon, metodo_pago=_metodo("Transferencia"))

        # Una pendiente (mercadería que todavía no llegó) y una anulada
        compras_services.crear_compra(
            proveedor=norte, usuario=self.u["lmamani"], numero_factura="A 0003-00004610",
            detalles=detalles(importados[:2], factor=1), observaciones="Llega la semana próxima",
        )
        anulada = compras_services.crear_compra(
            proveedor=valle, usuario=self.u["lmamani"], detalles=detalles(nacionales[:1]),
            observaciones="Cargada por error",
        )
        compras_services.anular_compra(compra=anulada)

    # ------------------------------------------------------------------ stock

    def _stock(self):
        for producto in self.P:
            deposito = Stock.objects.get(producto=producto, ubicacion=Stock.Ubicaciones.DEPOSITO)
            stock_services.registrar_reposicion(
                producto=producto, origen=Stock.Ubicaciones.DEPOSITO,
                cantidad=deposito.cantidad_actual // 2, usuario=self.u["mtolaba"], motivo="Reposición del salón",
            )
            caro = producto.precio_venta >= 50000
            Stock.objects.filter(producto=producto, ubicacion=Stock.Ubicaciones.SUCURSAL).update(
                stock_minimo=2 if caro else 4)
            Stock.objects.filter(pk=deposito.pk).update(stock_minimo=2 if caro else 4)

        # El último producto queda con stock bajo en el salón (aviso en el Inicio)
        bajo = Stock.objects.get(producto=self.P[-1], ubicacion=Stock.Ubicaciones.SUCURSAL)
        Stock.objects.filter(pk=bajo.pk).update(stock_minimo=bajo.cantidad_actual + 2)

        # Un ajuste por recuento
        stock_services.registrar_entrada(
            producto=self.P[1], ubicacion=Stock.Ubicaciones.DEPOSITO, cantidad=2,
            usuario=self.u["mtolaba"], motivo="Ajuste por recuento",
        )

    # ------------------------------------------------------------------ promociones

    def _promociones(self):
        hoy = date.today()
        T = Promocion.TipoDescuento
        barato = min(self.P, key=lambda p: p.precio_venta)

        promociones_services.crear_promocion(
            nombre="Semana Guinda", descripcion="15% en fragancias seleccionadas",
            tipo_descuento=T.PORCENTAJE, valor_descuento=Decimal("15"),
            fecha_inicio=hoy - timedelta(days=2), fecha_fin=hoy + timedelta(days=12),
            productos=[self.P[0], self.P[2]],
        )
        promociones_services.crear_promocion(
            nombre="Descuento en el más elegido", descripcion="$2.000 menos",
            tipo_descuento=T.MONTO_FIJO, valor_descuento=min(Decimal("2000"), _redondear(barato.precio_venta / 4)),
            fecha_inicio=hoy, fecha_fin=hoy + timedelta(days=30), productos=[barato],
        )
        promociones_services.crear_promocion(
            nombre="Día del Padre (vencida)", descripcion="Ya terminó: no se aplica",
            tipo_descuento=T.PORCENTAJE, valor_descuento=Decimal("20"),
            fecha_inicio=hoy - timedelta(days=60), fecha_fin=hoy - timedelta(days=50), productos=[self.P[1]],
        )
        promociones_services.crear_promocion(
            nombre="Navidad (futura)", descripcion="Todavía no empezó",
            tipo_descuento=T.PORCENTAJE, valor_descuento=Decimal("10"),
            fecha_inicio=hoy + timedelta(days=20), fecha_fin=hoy + timedelta(days=35), productos=[self.P[3]],
        )

    # ------------------------------------------------------------------ caja y ventas presenciales

    def _ventas_presenciales(self):
        vendedor, encargada = self.u["fcruz"], self.u["lmamani"]
        sofia = Cliente.objects.get(nro_documento="41235678")
        luis = Cliente.objects.get(nro_documento="28333444")

        def vender(items, pagos_por_metodo, cliente=None):
            total = _total(items)
            pagos = [_pago(m, total if monto is None else monto) for m, monto in pagos_por_metodo]
            if len(pagos) > 1:   # pago combinado: el último método completa el total
                pagos[-1]["monto"] = total - sum(p["monto"] for p in pagos[:-1])
            return ventas_services.registrar_venta_presencial(
                usuario=vendedor, caja=self.salon, items=items, cliente=cliente, pagos=pagos,
            )

        # ---- Turno mañana: ventas y cierre con un faltante de $500
        vender([_item(self.P[4], 1)], [("Efectivo", None)])
        vender([_item(self.P[1], 1)], [("Tarjeta de débito", None)], cliente=luis)
        if self.sesion_manana is not None:
            esperado = cajas_services.resumen_sesion(self.sesion_manana)["efectivo_esperado"]
            cajas_services.cerrar_caja(
                sesion=self.sesion_manana, monto_final=esperado - Decimal("500"),
                observaciones="Faltante de $500 (error de vuelto)",
            )

            # ---- Turno tarde: queda abierto para seguir probando
            cajas_services.abrir_caja(
                caja=self.salon, usuario=vendedor, monto_inicial=Decimal("30000"), observaciones="Turno tarde",
            )
        # Pago combinado: la mitad en efectivo y el resto con débito
        mitad = _redondear(_total([_item(self.P[0], 1)]) / 2)
        vender([_item(self.P[0], 1)], [("Efectivo", mitad), ("Tarjeta de débito", None)], cliente=sofia)
        vender([_item(self.P[5], 2)], [("Transferencia", None)])
        anulable = vender([_item(self.P[2], 1)], [("Efectivo", None)])
        ventas_services.anular_venta(venta=anulable, usuario=encargada, motivo="El cliente se arrepintió en el momento")

        cajas_services.registrar_movimiento_caja(
            caja=self.salon, tipo_movimiento=MovimientoCaja.TipoMovimiento.EGRESO,
            monto=Decimal("4500"), metodo_pago=_metodo("Efectivo"), concepto="Artículos de limpieza",
        )
        cajas_services.registrar_movimiento_caja(
            caja=self.salon, tipo_movimiento=MovimientoCaja.TipoMovimiento.INGRESO,
            monto=Decimal("10000"), metodo_pago=_metodo("Efectivo"), concepto="Refuerzo de cambio",
        )

    # ------------------------------------------------------------------ ventas online y envíos

    def _ventas_online(self):
        online = self.u["jarias"]
        E = Envio.EstadoEnvio
        web = {c[0]: Cliente.objects.get(usuario__username=c[0]) for c in CLIENTES_WEB}
        carla = Cliente.objects.get(nro_documento="27-39456781-4")
        martin = Cliente.objects.get(nro_documento="37889102")

        def venta(cliente, items, metodo, provincia=None, cp=None, direccion=None, usuario=online, mp=None, obs=None):
            costo = tarifa_envio(provincia, cp)["costo"] if provincia else None
            total = _total(items) + (costo or Decimal("0"))
            return ventas_services.registrar_venta_online(
                usuario=usuario, cliente=cliente, items=items, pagos=[_pago(metodo, total)],
                entrega="ENVIO" if provincia else "RETIRO", costo_envio=costo,
                direccion_entrega=direccion, observaciones=obs, mp_payment_id=mp,
            )

        def avanzar(v, *estados, empresa="Correo Argentino", codigo=None):
            envio = Envio.objects.get(venta=v)
            for estado in estados:
                envio = envios_services.cambiar_estado(
                    envio=envio, estado=estado, empresa_transporte=empresa, codigo_seguimiento=codigo,
                )

        # Retiro en el local
        venta(martin, [_item(self.P[3], 1)], "Transferencia", obs="Pidió por WhatsApp, retira en el local")

        # Compras de la tienda (como las registra el webhook; pagos SIMULADOS: no anularlas)
        v = venta(web["sbenitez"], [_item(self.P[0], 1)], "Mercado Pago", "Salta", "4400",
                  "Los Ceibos 245, B° Tres Cerritos, Salta (CP 4400)", usuario=web["sbenitez"].usuario,
                  mp="SIMULADO-0001", obs="Tienda web · pago SIMULADO (no anular)")
        avanzar(v, E.PREPARADO)
        v = venta(web["acortez"], [_item(self.P[2], 1)], "Mercado Pago", "Salta", "4427",
                  "Güemes 210, Cafayate, Salta (CP 4427)", usuario=web["acortez"].usuario,
                  mp="SIMULADO-0002", obs="Tienda web · pago SIMULADO (no anular)")
        avanzar(v, E.PREPARADO, E.DESPACHADO, codigo="CA483920175AR")
        v = venta(web["tquispe"], [_item(self.P[4], 2)], "Mercado Pago", "Jujuy", "4600",
                  "Belgrano 845, San Salvador de Jujuy, Jujuy (CP 4600)", usuario=web["tquispe"].usuario,
                  mp="SIMULADO-0003", obs="Tienda web · pago SIMULADO (no anular)")
        avanzar(v, E.PREPARADO, E.DESPACHADO, E.EN_TRANSITO, E.ENTREGADO, empresa="Andreani", codigo="AND-36001522")
        v = venta(web["nfarias"], [_item(self.P[1], 1)], "Mercado Pago", "Córdoba", "5000",
                  "Bv. San Juan 1020, Córdoba, Córdoba (CP 5000)", usuario=web["nfarias"].usuario,
                  mp="SIMULADO-0004", obs="Tienda web · pago SIMULADO (no anular)")
        avanzar(v, E.PREPARADO, E.DESPACHADO, E.DEMORADO, codigo="CA483920999AR")

        # Ventas online cargadas en el panel (transferencia)
        venta(carla, [_item(self.P[5], 1)], "Transferencia", "Salta", "4400", "Mitre 1180, Salta (CP 4400)")
        v = venta(martin, [_item(self.P[0], 1)], "Transferencia", "Salta", "4400", "Av. Bolivia 3120, Salta (CP 4400)")
        avanzar(v, E.PREPARADO, E.DESPACHADO, E.EN_TRANSITO, E.DEVUELTO, empresa="Cadetería Rápida")

    # ------------------------------------------------------------------ pedidos

    def _pedidos(self):
        P = Pedido.EstadoPedido
        vendedor, online = self.u["fcruz"], self.u["jarias"]
        sofia = Cliente.objects.get(nro_documento="41235678")
        martin = Cliente.objects.get(nro_documento="37889102")
        carla = Cliente.objects.get(nro_documento="27-39456781-4")
        luis = Cliente.objects.get(nro_documento="28333444")

        def pedido(cliente, canal, items, estados=(), usuario=vendedor, obs=None):
            p = pedidos_services.crear_pedido(cliente=cliente, canal=canal, items=items, usuario=usuario, observaciones=obs)
            for estado in estados:
                p = pedidos_services.cambiar_estado(pedido=p, estado=estado)
            return p

        pedido(sofia, "WHATSAPP", [_item(self.P[1], 1)], obs="Esperando la transferencia")
        pedido(martin, "INSTAGRAM", [_item(self.P[2], 1)], [P.RESERVADO], obs="Transferencia recibida")
        pedido(carla, "WHATSAPP", [_item(self.P[3], 1), _item(self.P[5], 1)], [P.RESERVADO, P.LISTO],
               usuario=online, obs="Retira el sábado por la tarde")

        entregado = pedido(luis, "PRESENCIAL", [_item(self.P[4], 1)], [P.RESERVADO, P.LISTO])
        total = sum(d.precio_referencia * d.cantidad for d in entregado.detallepedido_set.all())
        pedidos_services.entregar_pedido(
            pedido=entregado, usuario=online, pagos=[_pago("Transferencia", total)], entrega="RETIRO",
        )

        cancelado = pedido(sofia, "WHATSAPP", [_item(self.P[0], 1)])
        pedidos_services.cancelar_pedido(pedido=cancelado, motivo="La clienta desistió")

    # ================================================================== resúmenes

    def _resumen(self):
        self.stdout.write(self.style.SUCCESS("\nDemo cargada."))
        self.stdout.write(
            f"  Compras: {Compra.objects.count()} · Ventas: {Venta.objects.count()} "
            f"({Venta.objects.filter(estado='ANULADA').count()} anulada) · Envíos: {Envio.objects.count()} · "
            f"Pedidos: {Pedido.objects.count()} · Promociones: {Promocion.objects.count()} · "
            f"Sesiones de caja: {AperturaCierreCaja.objects.count()}"
        )
        self.stdout.write(f"\nCuentas de la demo (contraseña de todas: {PASSWORD})")
        for username, nombre, apellido, dni, _, roles in EMPLEADOS:
            usuario = _usuario_del_empleado(username, dni)
            self.stdout.write(f"  {usuario.username:<9} {nombre} {apellido} · {', '.join(roles)}")
        for username, nombre, apellido, *_ in CLIENTES_WEB:
            self.stdout.write(f"  {username:<9} {nombre} {apellido} · cliente de la tienda")


def _sin_tildes(texto):
    import unicodedata
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def _usuario_del_empleado(username, dni):
    """El usuario de la demo, o el del empleado con ese DNI si lo cargaron a mano."""
    Usuario = get_user_model()
    usuario = Usuario.objects.filter(username__iexact=username).first()
    if usuario is None:
        empleado = Empleado.objects.filter(dni=dni).first()
        usuario = empleado.usuario if empleado else None
    # Empleado cargado sin acceso al sistema: sus operaciones quedan a nombre del superusuario
    return usuario or Usuario.objects.filter(is_superuser=True).order_by("pk").first()


def _existe_usuario(username):
    return get_user_model().objects.filter(username__iexact=username).exists()
