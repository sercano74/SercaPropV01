from django.db import migrations

POSTULACION_TITLE = "Nueva postulación a corredor"
POSTULACION_TYPE = "postulacion"


def backfill(apps, schema_editor):
    """Marca las notificaciones de postulación a corredor creadas antes de que
    existiera `related_object_type`. Sin esto, el enlace del CDC caía en el
    fallback y abría /prop/solicitud/<id>/ (una solicitud de publicación)."""
    Communication = apps.get_model("a01Com", "Communication")
    Communication.objects.filter(
        title=POSTULACION_TITLE,
        related_object_type="",
    ).update(related_object_type=POSTULACION_TYPE)


def unbackfill(apps, schema_editor):
    Communication = apps.get_model("a01Com", "Communication")
    Communication.objects.filter(
        title=POSTULACION_TITLE,
        related_object_type=POSTULACION_TYPE,
    ).update(related_object_type="")


class Migration(migrations.Migration):

    dependencies = [
        ("a01Com", "0003_consultacontacto"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
