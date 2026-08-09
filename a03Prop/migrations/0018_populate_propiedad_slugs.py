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


def _nombre_comuna(p):
    """Nombre de la comuna o 'sin-comuna' si no tiene."""
    if p.comuna_id and p.comuna:
        return p.comuna.nombre
    return "sin-comuna"


def _base_slug(p):
    """Construye la base del slug con datos legibles."""
    comuna = slugify(_nombre_comuna(p)) or "sin-comuna"
    base = slugify(f"{p.tipo_accion}-{p.tipo_prop}-{comuna}-{p.id}")[:200]
    return base or f"propiedad-{p.id}"


def poblar_slugs(apps, schema_editor):
    """Asigna slug SEO a las propiedades sin slug.

    Usa QuerySet.update() (SQL puro) y el nombre REAL de la comuna
    (campo `nombre`), no el repr del objeto.
    """
    Propiedad = apps.get_model("a03Prop", "Propiedad")
    for p in Propiedad.objects.filter(slug__isnull=True).order_by("id"):
        slug = _slug_unico(Propiedad.objects, _base_slug(p))
        # Selecciona de nuevo el objeto para refrescar la FK comuna caché
        Propiedad.objects.filter(pk=p.pk).update(slug=slug)


def regen_slugs(apps, schema_editor):
    """(0019) Re-genera TODOS los slugs — arregla los generados con el
    repr de la comuna (ej. 'comuna-object-322') por el nombre real.
    """
    Propiedad = apps.get_model("a03Prop", "Propiedad")
    for p in Propiedad.objects.order_by("id"):
        old = p.slug
        # forzar re-lectura de la FK seteando a None y re-asignando
        p.comuna_id = p.comuna_id
        slug = _slug_unico(Propiedad.objects, _base_slug(p))
        if slug != old:
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
