"""Deja los planes de corredor con los dos nombres oficiales del sitio.

En producción quedaron dos planes de corredor con nombres de una versión
anterior —``Initial House`` y ``Premier House``— que no aparecen en ningún
template ni en ningún seed del repositorio: son filas que se cargaron a mano y
que sobrevivieron a los renombres. El resultado es que la página *Sé nuestro
agente*, que pinta los planes que haya en la base, ofrecía planes que no son los
del sitio y confundía tanto al postulante como a la gerencia.

La corrección **no borra los planes**: los renombra a ``Barrio`` y ``Metrópoli``
conservando precio, cupos, comisión e historial. ``Premier House`` no tiene
suscripciones, pero ``Initial House`` sí, y ``SuscripcionCorredor.plan`` es
``PROTECT``: borrarlo habría roto a esa corredora. Renombrar arregla el nombre
visible sin tocar a nadie.

Si el plan destino ya existiera (por ejemplo, si alguien lo creó a mano con el
nombre correcto), las suscripciones y postulaciones del plan viejo se mueven al
destino y el duplicado se elimina, para no dejar dos planes con el mismo nombre
en la lista.
"""
from django.db import migrations

# Nombres heredados -> nombre oficial. Se comparan sin distinguir mayúsculas
# porque en la base conviven variantes escritas a mano.
RENOMBRES = [
    ("Initial House", "Barrio"),
    ("Premier House", "Metrópoli"),
]


def renombrar_planes(apps, schema_editor):
    PlanSuscripcion = apps.get_model("a00seg", "PlanSuscripcion")
    SuscripcionCorredor = apps.get_model("a00seg", "SuscripcionCorredor")
    SuscripcionVendedor = apps.get_model("a00seg", "SuscripcionVendedor")
    SolicitudCorredor = apps.get_model("a00seg", "SolicitudCorredor")

    for nombre_viejo, nombre_nuevo in RENOMBRES:
        origen = PlanSuscripcion.objects.filter(nombre__iexact=nombre_viejo).first()
        if origen is None:
            continue

        destino = (
            PlanSuscripcion.objects.filter(nombre__iexact=nombre_nuevo)
            .exclude(pk=origen.pk)
            .first()
        )

        if destino is None:
            origen.nombre = nombre_nuevo
            origen.save(update_fields=["nombre"])
            continue

        # Ya existe el plan bueno: se mueve todo lo que apunta al viejo.
        SuscripcionCorredor.objects.filter(plan=origen).update(plan=destino)
        SuscripcionVendedor.objects.filter(plan=origen).update(plan=destino)
        SolicitudCorredor.objects.filter(plan=origen).update(plan=destino)
        origen.delete()


def sin_reversion(apps, schema_editor):
    """Hacia atrás no se restauran los nombres viejos.

    "Initial House" y "Premier House" son justamente lo que confundía; volver a
    escribirlos reintroduciría el problema. Si hiciera falta, la gerencia
    renombra desde Gestión → Planes de corredor.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("a00seg", "0012_representacion_habilitada_por_defecto"),
    ]

    operations = [
        migrations.RunPython(renombrar_planes, sin_reversion),
    ]
