from django.db import migrations


def crear_mercado_pago(apps, schema_editor):
    """Método con el que se registran los cobros de la tienda web (webhook de Mercado Pago)."""
    MetodoPago = apps.get_model("cajas", "MetodoPago")
    metodo = MetodoPago.objects.filter(nombre__iexact="Mercado Pago").first()
    if metodo is None:
        MetodoPago.objects.create(nombre="Mercado Pago", estado=True)
    else:
        metodo.nombre = "Mercado Pago"
        metodo.estado = True
        metodo.save()


class Migration(migrations.Migration):

    dependencies = [
        ("cajas", "0003_metodo_efectivo"),
    ]

    operations = [
        migrations.RunPython(crear_mercado_pago, migrations.RunPython.noop),
    ]
