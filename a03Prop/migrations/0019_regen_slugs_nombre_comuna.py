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


def regen_slugs(apps, schema_editor):
    """Re-genera TODOS los slugs.

    En el deploy anterior la migración 0018 usó `str(p.comuna)` que en
    Postgres/con datos históricos devolvía el repr del objeto
    (ej. 'Comuna object (322)'), generando URLs como
    '/arriendo-departamento-comuna-object-322-2/'. Esta migración
    reconstruye los slugs con el NOMBRE real de la comuna (campo `nombre`).
    """
    Propiedad = apps.get_model("a03Prop", "Propiedad")
    for p in Propiedad.objects.order_by("id"):
        if p.comuna_id and p.comuna:
            comuna = slugify(p.comuna.nombre)
        else:
            comuna = "sin-comuna"
        comuna = comuna or "sin-comuna"
        base = slugify(f"{p.tipo_accion}-{p.tipo_prop}-{comuna}-{p.id}")[:200]
        base = base or f"propiedad-{p.id}"
        slug = _slug_unico(Propiedad.objects, base)
        if slug != p.slug:
            Propiedad.objects.filter(pk=p.pk).update(slug=slug)


def reverso(apps, schema_editor):
    """No reversible: no restauramos los slugs anteriores."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("a03Prop", "0018_populate_propiedad_slugs"),
    ]

    operations = [
        migrations.RunPython(regen_slugs, reverso),
    ]
