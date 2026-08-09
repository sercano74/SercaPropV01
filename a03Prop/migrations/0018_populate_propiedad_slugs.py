from django.db import migrations
from django.utils.text import slugify


def _slug_unico(modelos, base):
    """Genera un slug único agregando sufijo numérico si hay colisión."""
    slug = base
    contador = 1
    while modelos.filter(slug=slug).exists():
        slug = f"{base}-{contador}"
        contador += 1
    return slug


def poblar_slugs(apps, schema_editor):
    """Asigna slug SEO a todas las propiedades existentes sin slug.

    Usa QuerySet.update() (exactamente un UPDATE en SQL) para evitar
    triggers/validaciones de save(); en Postgres un UPDATE directo con un
    valor único no colisiona y si un slug ya existe se añade sufijo.
    """
    Propiedad = apps.get_model("a03Prop", "Propiedad")
    for p in Propiedad.objects.filter(slug__isnull=True).order_by("id"):
        if p.comuna_id:
            comuna = str(p.comuna).lower()
        else:
            comuna = "sin-comuna"
        comuna = slugify(comuna) or "sin-comuna"
        base = slugify(f"{p.tipo_accion}-{p.tipo_prop}-{comuna}-{p.id}")[:200] or f"propiedad-{p.id}"
        slug = _slug_unico(Propiedad, base)
        # update() → SQL puro, sin tocar otras columnas ni updated_at
        Propiedad.objects.filter(pk=p.pk).update(slug=slug)


def reverso(apps, schema_editor):
    """No reversible: los slugs generados no se revierten."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("a03Prop", "0017_propiedad_slug"),
    ]

    operations = [
        migrations.RunPython(poblar_slugs, reverso),
    ]
