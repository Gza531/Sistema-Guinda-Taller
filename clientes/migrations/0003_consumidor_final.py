from django.db import migrations


def crear_consumidor_final(apps, schema_editor):
    Cliente = apps.get_model("clientes", "Cliente")
    Cliente.objects.get_or_create(
        nombre="Consumidor",
        apellido="Final",
        nro_documento=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(crear_consumidor_final, migrations.RunPython.noop),
    ]
