from django.db import migrations, models


def pasar_a_pendiente(apps, schema_editor):
    """
    Los pedidos se pagan por adelantado: ya no se toman sin stock, así que el estado
    «En espera de stock» desaparece. Los que hubiera vuelven a Pendiente.
    """
    Pedido = apps.get_model("pedidos", "Pedido")
    Pedido.objects.filter(estado="EN_ESPERA_STOCK").update(estado="PENDIENTE")


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0003_sin_mercado_libre"),
    ]

    operations = [
        migrations.RunPython(pasar_a_pendiente, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pedido",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente"),
                    ("RESERVADO", "Reservado"),
                    ("LISTO", "Listo"),
                    ("ENTREGADO", "Entregado"),
                    ("CANCELADO", "Cancelado"),
                ],
                default="PENDIENTE",
                max_length=20,
            ),
        ),
    ]
