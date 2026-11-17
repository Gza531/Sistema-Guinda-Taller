from django.db import migrations, models


def habilitar_en_caja_online(apps, schema_editor):
    """
    La caja online cobra con Mercado Pago (tienda web) y con transferencia
    (pedidos por WhatsApp o Instagram, que se pagan por adelantado).
    Tarjetas y efectivo quedan solo para la caja presencial.
    """
    MetodoPago = apps.get_model("cajas", "MetodoPago")
    MetodoPago.objects.filter(nombre__iexact="Mercado Pago").update(en_caja_online=True)
    MetodoPago.objects.filter(nombre__icontains="transferencia").update(en_caja_online=True)


class Migration(migrations.Migration):

    dependencies = [
        ("cajas", "0004_metodo_mercado_pago"),
    ]

    operations = [
        migrations.AddField(
            model_name="metodopago",
            name="en_caja_online",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(habilitar_en_caja_online, migrations.RunPython.noop),
    ]
