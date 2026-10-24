from django.db import migrations

# Los roles del sistema son grupos de Django (ROLES y USUARIOS_X_ROLES del DER).
# Los nombres tienen que coincidir con los de core/permissions.py.
ROLES = [
    "Dueña",
    "Encargada",
    "Vendedor",
    "Responsable de stock",
    "Responsable de ventas online",
    "Cliente",
]


def crear_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nombre in ROLES:
        Group.objects.get_or_create(name=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ("seguridad", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        # Al revertir no se borran: podrían tener usuarios asignados.
        migrations.RunPython(crear_grupos, migrations.RunPython.noop),
    ]
