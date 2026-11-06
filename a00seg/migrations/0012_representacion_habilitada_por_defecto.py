"""Un plan de corredor nace pudiendo representar, no bloqueado.

Dos mitades del mismo arreglo:

1. **El defecto del campo.** ``permite_representacion`` nació en ``False``
   (migración 0009). Eso convertía la regla general —un corredor publica
   propiedades de terceros, es su trabajo— en la excepción, y obligaba a
   recordar activar el permiso plan por plan. Cada plan de corredor creado
   después de la 0011 volvía a nacer bloqueado, y la corredora sólo lo
   descubría al llegar al paso 1 con la opción deshabilitada. Ahora nace en
   ``True``: restringirlo es una decisión explícita de la gerencia, no el
   estado por omisión.

2. **Los planes que quedaron atrás.** La 0011 habilitó el permiso en los
   planes de corredor activos que existían en ese momento. Cualquier plan
   creado después, o desmarcado por error, sigue bloqueando la representación
   en producción. Esta migración los vuelve a habilitar.

Sólo se tocan planes de corredor **activos**. Un plan inactivo no lo opera
nadie y su estado no es un accidente que haya que corregir; y los planes de
vendedor no hacen representación, así que su valor no se interpreta igual.
"""
from django.db import migrations, models


def habilitar_en_planes_de_corredor(apps, schema_editor):
    PlanSuscripcion = apps.get_model("a00seg", "PlanSuscripcion")
    PlanSuscripcion.objects.filter(
        tipo="corredor", activo=True, permite_representacion=False
    ).update(permite_representacion=True)


def sin_reversion(apps, schema_editor):
    """Hacia atrás no se restaura el bloqueo.

    El valor anterior era el ``False`` por defecto del campo, que no
    significaba una decisión de nadie. Volver a ponerlo reintroduciría
    exactamente el bloqueo que esta migración corrige.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("a00seg", "0011_habilitar_representacion_en_planes_corredor"),
    ]

    operations = [
        migrations.AlterField(
            model_name="plansuscripcion",
            name="permite_representacion",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Desmárcalo sólo si quieres restringir este plan. La "
                    "gerencia lo administra en Gestión → Planes de corredor."
                ),
                verbose_name="Permite publicar en representación",
            ),
        ),
        migrations.RunPython(
            habilitar_en_planes_de_corredor,
            sin_reversion,
        ),
    ]
