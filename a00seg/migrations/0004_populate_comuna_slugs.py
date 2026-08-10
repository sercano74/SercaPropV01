# Poblar slugs de comunas existentes (para landing pages SEO por comuna).
from django.db import migrations
from django.utils.text import slugify


def populate_comuna_slugs(apps, schema_editor):
    Comuna = apps.get_model("a00seg", "Comuna")
    usados = set()
    for comuna in Comuna.objects.all().order_by("id"):
        base = slugify(comuna.nombre) or "comuna"
        slug = base
        contador = 1
        while slug in usados:
            slug = f"{base}-{contador}"
            contador += 1
        usados.add(slug)
        # Actualizar con update() para no disparar el save() del modelo real
        # (que solo genera slug si está vacío) y evitar colisiones únicas.
        Comuna.objects.filter(pk=comuna.pk).update(slug=slug)


def reverse_populate_comuna_slugs(apps, schema_editor):
    Comuna = apps.get_model("a00seg", "Comuna")
    Comuna.objects.update(slug=None)


class Migration(migrations.Migration):

    dependencies = [
        ("a00seg", "0003_comuna_slug"),
    ]

    operations = [
        migrations.RunPython(populate_comuna_slugs, reverse_populate_comuna_slugs),
    ]
