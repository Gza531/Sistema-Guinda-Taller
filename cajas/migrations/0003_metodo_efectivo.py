from django.db import migrations


def crear_efectivo(apps, schema_editor):
    MetodoPago = apps.get_model("cajas", "MetodoPago")
    efectivo = MetodoPago.objects.filter(nombre__iexact="Efectivo").first()
    if efectivo is None:
        MetodoPago.objects.create(nombre="Efectivo", estado=True)
    else:
        efectivo.nombre = "Efectivo"
        efectivo.estado = True
        efectivo.save()


class Migration(migrations.Migration):

    dependencies = [
        ("cajas", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(crear_efectivo, migrations.RunPython.noop),
    ]
