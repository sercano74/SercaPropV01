# Generated manually - Campo orden para Funcionario (orden de cards en /nosotros/)

from django.db import migrations, models


def asignar_ordenes(apps, schema_editor):
    """Asigna el orden de los funcionarios por nombre.

    Sergio -> 1, Francia -> 200, Patricia -> 300.
    Usa icontains para tolerar nombres completos distintos
    (ej. 'Sergio Cannobbio', 'Francia Pérez', 'Patricia ...').
    """
    Funcionario = apps.get_model("a00seg", "Funcionario")
    ordenes = [
        ("sergio", 1),
        ("francia", 200),
        ("patricia", 300),
    ]
    for nombre_busqueda, orden in ordenes:
        Funcionario.objects.filter(
            nombre_completo__icontains=nombre_busqueda
        ).update(orden=orden)


def reverso(apps, schema_editor):
    """No reversible: los valores de orden no se revierten."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("a00seg", "0006_documentogestion"),
    ]

    operations = [
        migrations.AddField(
            model_name="funcionario",
            name="orden",
            field=models.PositiveSmallIntegerField(
                default=0,
                verbose_name="Orden",
                help_text="Menor número = aparece primero. Usa 1, 200, 300... para dejar espacio entre funcionarios.",
            ),
        ),
        migrations.RunPython(asignar_ordenes, reverso),
        migrations.AlterModelOptions(
            name="funcionario",
            options={
                "verbose_name": "Funcionario",
                "verbose_name_plural": "Funcionarios",
                "ordering": ["orden", "id"],
            },
        ),
    ]
