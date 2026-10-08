"""Alinea el cupo mensual de publicaciones con la capacidad de cada plan.

``max_publicaciones_mensual`` se agregó con ``default=5``, así que **todas** las
filas existentes quedaron con 5, incluidas las de un plan cuya capacidad real es
mayor. El efecto era silencioso: un corredor del plan grande quedaba topado a 5
publicaciones al mes en vez de a 15, porque ``representacion.cupo_del_mes``
compara contra ese número.

El dato que revela cuál era la intención ya estaba en la misma fila:
``max_propiedades_simultaneas``. Los dos campos describen la misma capacidad
—cuánto puede llevar el corredor— y se crearon para coincidir, así que este
cupo se siembra desde ahí.

Si la gerencia quiere un cupo distinto del de propiedades simultáneas, lo ajusta
después en Gestión → Planes de corredor, que es el motivo por el que esa pantalla
existe. Esta migración sólo deja de partir a todos del mismo valor.
"""
from django.db import migrations


def sembrar_cupo_desde_capacidad(apps, schema_editor):
    PlanSuscripcion = apps.get_model("a00seg", "PlanSuscripcion")
    for plan in PlanSuscripcion.objects.all():
        if plan.max_publicaciones_mensual != plan.max_propiedades_simultaneas:
            plan.max_publicaciones_mensual = plan.max_propiedades_simultaneas
            plan.save(update_fields=["max_publicaciones_mensual"])


class Migration(migrations.Migration):

    dependencies = [
        ("a00seg", "0009_plansuscripcion_max_publicaciones_mensual_and_more"),
    ]

    operations = [
        migrations.RunPython(
            sembrar_cupo_desde_capacidad,
            # Hacia atrás no hay nada que restaurar: el valor anterior era el
            # ``default=5`` del campo, que no significaba nada para cada plan.
            migrations.RunPython.noop,
        ),
    ]
