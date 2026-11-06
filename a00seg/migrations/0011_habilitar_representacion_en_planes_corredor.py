"""Habilita la representación en los planes de corredor que ya existían.

``permite_representacion`` se agregó en la migración 0009 con
``default=False``, así que **todas** las filas existentes quedaron sin el
permiso, incluidas las de un plan que sí debía permitir publicar propiedades de
terceros. El efecto era silencioso y de bloqueo total: un corredor con plan
vigente abría el paso 1, la opción "Represento al propietario" aparecía
deshabilitada y no había nada en el flujo que explicara por qué ni cómo
arreglarlo. Es el caso reportado por la corredora del plan grande.

La gerencia puede habilitarlo plan por plan desde *Gestión → Planes de
corredor*; lo que faltaba era el punto de partida, porque nadie había activado
el permiso para ningún plan. Esta migración deja los planes de corredor
**activos** en un estado coherente con lo que la plataforma ya venía haciendo
—publicar en representación es la razón de ser de los corredores de la
correduría— y deja la pantalla de gerencia como el lugar donde se ajusta hacia
adelante.

No se tocan los planes de vendedor: la representación es un caso de corredor.
Un plan inactivo tampoco se toca, porque nadie lo opera.

Si la gerencia quiere un plan de corredor sin representación, lo desmarca en la
pantalla: esta migración no impone nada que la aplicación no pueda revertir.
"""
from django.db import migrations


def habilitar_representacion(apps, schema_editor):
    PlanSuscripcion = apps.get_model("a00seg", "PlanSuscripcion")
    plan_corredor_activo = PlanSuscripcion.objects.filter(
        tipo="corredor", activo=True, permite_representacion=False
    )
    plan_corredor_activo.update(permite_representacion=True)


class Migration(migrations.Migration):

    dependencies = [
        ("a00seg", "0010_cupo_mensual_segun_plan"),
    ]

    operations = [
        migrations.RunPython(
            habilitar_representacion,
            # Hacia atrás no hay nada que restaurar: el valor anterior era el
            # ``default=False`` del campo, que no significaba nada para cada
            # plan. Volver a dejarlos todos en False reintroduciría el bloqueo.
            migrations.RunPython.noop,
        ),
    ]
