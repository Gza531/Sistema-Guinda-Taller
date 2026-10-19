"""
Reglas de negocio de las fotos de productos.

- Hasta MAX_IMAGENES fotos por producto, de hasta 2 MB, en JPG, PNG o WEBP.
- La primera foto que se sube queda como principal.
- Las fotos se borran de verdad (registro y archivo).
"""

from django.db import transaction
from django.db.models import Max
from PIL import Image
from rest_framework.exceptions import ValidationError

from .models import ImagenProducto, Producto

MAX_IMAGENES = 4
MAX_BYTES = 2 * 1024 * 1024
FORMATOS = {"JPEG", "JPG", "PNG", "WEBP"}


def _validar_archivo(archivo):
    if archivo.size > MAX_BYTES:
        raise ValidationError({
            "imagenes": f"«{archivo.name}» pesa más de 2 MB."
        })

    try:
        with Image.open(archivo) as img:
            formato = img.format
            img.verify()
    except Exception:
        raise ValidationError({
            "imagenes": f"«{archivo.name}» no es una imagen válida."
        })
    finally:
        archivo.seek(0)

    if formato not in FORMATOS:
        raise ValidationError({
            "imagenes": f"«{archivo.name}» tiene que ser JPG, PNG o WEBP."
        })


@transaction.atomic
def agregar_imagenes(*, producto, archivos):
    # Se bloquea el producto para que dos subidas a la vez no pasen el límite
    producto = Producto.objects.select_for_update().get(pk=producto.pk)
    actuales = producto.imagenes.count()

    if actuales + len(archivos) > MAX_IMAGENES:
        lugar = MAX_IMAGENES - actuales
        if lugar == 0:
            detalle = "Ya tiene todas; borre alguna para subir otra."
        else:
            detalle = f"Ya tiene {actuales}; puede agregar {lugar} más."

        raise ValidationError({
            "imagenes": f"Un producto puede tener hasta {MAX_IMAGENES} fotos. {detalle}"
        })

    for archivo in archivos:
        _validar_archivo(archivo)

    hay_principal = producto.imagenes.filter(es_principal=True).exists()
    ultimo_orden = producto.imagenes.aggregate(m=Max("orden"))["m"] or 0

    creadas = []
    for i, archivo in enumerate(archivos, start=1):
        creadas.append(ImagenProducto.objects.create(
            producto=producto,
            imagen=archivo,
            orden=ultimo_orden + i,
            es_principal=(not hay_principal and i == 1),
        ))

    return creadas


@transaction.atomic
def marcar_principal(*, imagen):
    Producto.objects.select_for_update().get(pk=imagen.producto_id)

    ImagenProducto.objects.filter(
        producto_id=imagen.producto_id, es_principal=True
    ).update(es_principal=False)

    imagen.es_principal = True
    imagen.save(update_fields=["es_principal"])
    return imagen


@transaction.atomic
def ordenar_imagenes(*, producto, ids):
    actuales = set(producto.imagenes.values_list("pk", flat=True))

    if len(ids) != len(set(ids)) or set(ids) != actuales:
        raise ValidationError({
            "orden": "Mande los ids de todas las fotos del producto, una vez cada una."
        })

    for posicion, pk in enumerate(ids, start=1):
        ImagenProducto.objects.filter(pk=pk).update(orden=posicion)


@transaction.atomic
def eliminar_imagen(*, imagen):
    producto = Producto.objects.select_for_update().get(pk=imagen.producto_id)
    era_principal = imagen.es_principal
    archivo = imagen.imagen

    imagen.delete()

    # Si se borró la principal, pasa a serlo la siguiente en el orden
    if era_principal:
        siguiente = producto.imagenes.first()
        if siguiente:
            siguiente.es_principal = True
            siguiente.save(update_fields=["es_principal"])

    # El archivo se borra recién cuando la base confirma el cambio
    transaction.on_commit(lambda: archivo.storage.delete(archivo.name))