from decimal import Decimal

from django.db import migrations, models
from django.db.models import Sum


def marcar_cobrados(apps, schema_editor):
    """
    Envíos que ya existían: el costo se cobró en la venta si el total de la venta
    es la suma de sus productos más el costo del envío.
    """
    Envio = apps.get_model("envios", "Envio")
    DetalleVenta = apps.get_model("ventas", "DetalleVenta")

    for envio in Envio.objects.filter(costo__isnull=False).select_related("venta"):
        productos = DetalleVenta.objects.filter(venta_id=envio.venta_id).aggregate(
            total=Sum("subtotal")
        )["total"] or Decimal("0.00")
        if envio.venta.total == productos + envio.costo:
            envio.costo_cobrado = True
            envio.save(update_fields=["costo_cobrado"])


class Migration(migrations.Migration):

    dependencies = [
        ("envios", "0003_alter_envio_estado"),
        ("ventas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="envio",
            name="costo_cobrado",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(marcar_cobrados, migrations.RunPython.noop),
    ]
