"""
Carga datos de prueba para desarrollar y probar el sistema.

Uso:
    docker compose exec web python manage.py cargar_datos_prueba

Se puede correr varias veces: lo que ya existe no se duplica.
Requiere haber creado antes un superusuario (createsuperuser).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cajas.models import Caja, MetodoPago
from catalogo.models import Categoria, Marca, Producto
from clientes.models import Cliente
from compras import services as compras_services
from compras.models import Compra
from proveedores.models import Proveedor, ProveedorXProducto
from stock import services as stock_services
from stock.models import Stock

MARCAS = ["Dior", "Chanel", "Carolina Herrera", "Paco Rabanne", "Maybelline", "L'Oréal", "Natura"]
CATEGORIAS = ["Perfumes", "Maquillaje", "Desodorantes", "Accesorios"]

# nombre, marca, categoría, género, origen, volumen, precio, (salón, depósito, mínimo)
PRODUCTOS = [
    ("Miss Dior EDP", "Dior", "Perfumes", "FEMENINO", "IMPORTADO", "100 ml", "185000", (4, 10, 3)),
    ("Sauvage EDT", "Dior", "Perfumes", "MASCULINO", "IMPORTADO", "100 ml", "172000", (2, 6, 3)),
    ("Chanel N°5 EDP", "Chanel", "Perfumes", "FEMENINO", "IMPORTADO", "50 ml", "210000", (1, 0, 2)),
    ("212 VIP Men", "Carolina Herrera", "Perfumes", "MASCULINO", "IMPORTADO", "100 ml", "158000", (5, 8, 3)),
    ("Good Girl EDP", "Carolina Herrera", "Perfumes", "FEMENINO", "IMPORTADO", "80 ml", "168000", (3, 4, 2)),
    ("1 Million EDT", "Paco Rabanne", "Perfumes", "MASCULINO", "IMPORTADO", "100 ml", "149000", (6, 12, 4)),
    ("Máscara Lash Sensational", "Maybelline", "Maquillaje", "NO_APLICA", "IMPORTADO", None, "18500", (15, 30, 10)),
    ("Labial SuperStay Matte Ink", "Maybelline", "Maquillaje", "NO_APLICA", "IMPORTADO", None, "16900", (8, 20, 10)),
    ("Base True Match", "L'Oréal", "Maquillaje", "NO_APLICA", "IMPORTADO", "30 ml", "24500", (6, 10, 5)),
    ("Desodorante Kaiak", "Natura", "Desodorantes", "MASCULINO", "NACIONAL", "75 g", "9800", (20, 40, 10)),
    ("Desodorante Ekos", "Natura", "Desodorantes", "UNISEX", "NACIONAL", "75 g", "9200", (0, 25, 10)),
]

CLIENTES = [
    ("Ana", "Pérez", "DNI", "30111222", "3874111222", "ana.perez@mail.com", "Belgrano 123, Salta"),
    ("Luis", "Gómez", "DNI", "28333444", "3874333444", None, "Mitre 456, Salta"),
    ("Sol", "Ruiz", "DNI", "35555666", "3875555666", "sol.ruiz@mail.com", None),
    ("Distribuidora", "Norte SRL", "CUIT", "30-71234567-8", "3874999000", "compras@norte.com", "Av. Bolivia 2000, Salta"),
]

PROVEEDORES = [
    ("Perfumería Mayorista del Norte", "30-70111222-3", "3874000111", "ventas@mayoristanorte.com",
     ["Miss Dior EDP", "Sauvage EDT", "Chanel N°5 EDP", "212 VIP Men", "Good Girl EDP", "1 Million EDT"]),
    ("Cosméticos Andinos SA", "30-70333444-5", "3874000222", "pedidos@andinos.com",
     ["Máscara Lash Sensational", "Labial SuperStay Matte Ink", "Base True Match"]),
    ("Natura Distribución Salta", "30-70555666-7", "3874000333", None,
     ["Desodorante Kaiak", "Desodorante Ekos"]),
]

METODOS_PAGO = ["Débito", "Crédito", "Transferencia", "Mercado Pago"]


class Command(BaseCommand):
    help = "Carga datos de prueba (catálogo, stock, clientes, proveedores, cajas, compras)."

    @transaction.atomic
    def handle(self, *args, **options):
        usuario = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        if usuario is None:
            raise CommandError(
                "Primero creá un superusuario: python manage.py createsuperuser"
            )

        marcas = {n: Marca.objects.get_or_create(nombre=n)[0] for n in MARCAS}
        categorias = {n: Categoria.objects.get_or_create(nombre=n)[0] for n in CATEGORIAS}

        productos = {}
        for nombre, marca, cat, genero, origen, volumen, precio, (salon, deposito, minimo) in PRODUCTOS:
            producto, _ = Producto.objects.get_or_create(
                nombre=nombre,
                marca=marcas[marca],
                defaults=dict(
                    categoria=categorias[cat], genero_producto=genero, origen=origen,
                    volumen=volumen, precio_venta=Decimal(precio),
                ),
            )
            productos[nombre] = producto
            for ubicacion, cantidad in ((Stock.Ubicaciones.SUCURSAL, salon), (Stock.Ubicaciones.DEPOSITO, deposito)):
                if Stock.objects.filter(producto=producto, ubicacion=ubicacion).exists():
                    continue
                if cantidad > 0:
                    stock_services.registrar_entrada(
                        producto=producto, ubicacion=ubicacion, cantidad=cantidad,
                        usuario=usuario, motivo="Stock inicial (datos de prueba)",
                    )
                    stock = Stock.objects.get(producto=producto, ubicacion=ubicacion)
                else:
                    stock = Stock.objects.create(producto=producto, ubicacion=ubicacion)
                stock.stock_minimo = minimo
                stock.save(update_fields=["stock_minimo"])

        for nombre, apellido, tipo_doc, doc, tel, email, direccion in CLIENTES:
            Cliente.objects.get_or_create(
                nro_documento=doc,
                defaults=dict(nombre=nombre, apellido=apellido, tipo_documento=tipo_doc,
                              telefono=tel, email=email, direccion=direccion),
            )

        proveedores = {}
        for razon, cuit, tel, email, prods in PROVEEDORES:
            proveedor, _ = Proveedor.objects.get_or_create(
                cuit=cuit, defaults=dict(razon_social=razon, telefono=tel, email=email),
            )
            proveedores[razon] = proveedor
            for nombre in prods:
                ProveedorXProducto.objects.get_or_create(
                    proveedor=proveedor, producto=productos[nombre],
                    defaults=dict(precio_compra_referencia=(productos[nombre].precio_venta * Decimal("0.6")).quantize(Decimal("0.01"))),
                )

        for nombre in METODOS_PAGO:
            MetodoPago.objects.get_or_create(nombre=nombre)

        Caja.objects.get_or_create(nombre="Caja salón", defaults=dict(tipo_caja=Caja.TipoCaja.PRESENCIAL))
        Caja.objects.get_or_create(nombre="Caja online", defaults=dict(tipo_caja=Caja.TipoCaja.ONLINE))

        if not Compra.objects.exists():
            mayorista = proveedores["Perfumería Mayorista del Norte"]
            recibida = compras_services.crear_compra(
                proveedor=mayorista, usuario=usuario, numero_factura="A-0001-00001234",
                detalles=[
                    {"producto": productos["Sauvage EDT"], "cantidad": 3, "precio_unitario": Decimal("103000")},
                    {"producto": productos["1 Million EDT"], "cantidad": 2, "precio_unitario": Decimal("89000")},
                ],
            )
            compras_services.recibir_compra(compra=recibida, usuario=usuario)
            compras_services.crear_compra(
                proveedor=proveedores["Cosméticos Andinos SA"], usuario=usuario,
                observaciones="Pedido semanal de maquillaje",
                detalles=[
                    {"producto": productos["Máscara Lash Sensational"], "cantidad": 24, "precio_unitario": Decimal("11000")},
                    {"producto": productos["Labial SuperStay Matte Ink"], "cantidad": 12, "precio_unitario": Decimal("10100")},
                ],
            )

        self.stdout.write(self.style.SUCCESS(
            f"Datos de prueba listos: {Producto.objects.count()} productos, "
            f"{Cliente.objects.count()} clientes, {Proveedor.objects.count()} proveedores, "
            f"{MetodoPago.objects.count()} métodos de pago, {Caja.objects.count()} cajas, "
            f"{Compra.objects.count()} compras."
        ))
