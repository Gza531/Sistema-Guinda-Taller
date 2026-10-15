from django.db import migrations


def normalizar_estados(apps, schema_editor):
    Compra = apps.get_model("compras", "Compra")

    Compra.objects.filter(estado="pendiente").update(estado="PENDIENTE")
    Compra.objects.filter(estado="recibida").update(estado="RECIBIDA")
    Compra.objects.filter(estado="anulada").update(estado="ANULADA")


def revertir_estados(apps, schema_editor):
    Compra = apps.get_model("compras", "Compra")

    Compra.objects.filter(estado="PENDIENTE").update(estado="pendiente")
    Compra.objects.filter(estado="RECIBIDA").update(estado="recibida")
    Compra.objects.filter(estado="ANULADA").update(estado="anulada")


class Migration(migrations.Migration):

    dependencies = [
        ("compras", "0003_alter_compra_estado"),
    ]

    operations = [
        migrations.RunPython(
            normalizar_estados,
            revertir_estados,
        ),
    ]