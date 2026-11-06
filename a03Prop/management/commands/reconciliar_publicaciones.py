"""Saca de la vitrina las propiedades cuya publicación no cumplió sus etapas.

Contexto
--------
Una propiedad se muestra en el home si tiene una ``PublicacionProp`` en estado
``publicada``. El proceso de cinco etapas vive aparte, en
``SolicitudPublicacion``. Cuando los dos objetos quedan desincronizados —una
propiedad "publicada" mientras su solicitud sigue en el paso 3—, la vitrina
muestra algo que no debiera existir. Le pasó a las propiedades 8 y 9: se
publicaron sin mandato ni Orden de Gestión.

Este comando reconcilia el estado hacia la regla correcta: si la solicitud de
una propiedad todavía no llegó a ``publicada``, su ``PublicacionProp`` se
archiva y la propiedad vuelve a ``borrador``. No inventa etapas: sólo retira de
la vitrina lo que no las cumplió, para que el responsable termine el proceso.

Uso::

    python manage.py reconciliar_publicaciones --dry-run
    python manage.py reconciliar_publicaciones --ids 8 9
    python manage.py reconciliar_publicaciones
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from a03Prop import publicacion
from a03Prop.models import Propiedad, PublicacionProp


class Command(BaseCommand):
    help = (
        "Archiva las publicaciones visibles cuya solicitud no completó las "
        "cinco etapas, y devuelve esas propiedades a borrador."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ids",
            nargs="*",
            type=int,
            default=None,
            help="IDs de propiedad a revisar. Si se omite, revisa todas.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra lo que haría sin guardar ningún cambio.",
        )

    def handle(self, *args, **options):
        ids = options.get("ids")
        dry_run = options.get("dry_run")

        publicaciones = PublicacionProp.objects.filter(
            estado="publicada"
        ).select_related("propiedad")
        if ids:
            publicaciones = publicaciones.filter(propiedad_id__in=ids)

        incoherentes = []
        for pub in publicaciones:
            solicitud = publicacion.solicitud_activa(pub.propiedad)
            if solicitud is None or solicitud.estado == publicacion.ESTADO_PUBLICADA:
                continue
            incoherentes.append((pub, solicitud))

        if not incoherentes:
            self.stdout.write(self.style.SUCCESS(
                "No hay publicaciones fuera de etapa. Nada que reconciliar."
            ))
            return

        for pub, solicitud in incoherentes:
            linea = (
                f"Propiedad #{pub.propiedad_id}: publicación #{pub.id} en "
                f"'publicada' pero la solicitud #{solicitud.id} está en "
                f"'{solicitud.get_estado_display()}'. "
            )
            if dry_run:
                self.stdout.write(self.style.WARNING("[dry-run] " + linea + "Se archivaría."))
            else:
                self._reconciliar(pub, solicitud)
                self.stdout.write(self.style.SUCCESS(linea + "Archivada y devuelta a borrador."))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"{len(incoherentes)} publicación(es) se reconciliarían. "
                "Ejecuta sin --dry-run para aplicarlo."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"{len(incoherentes)} publicación(es) reconciliada(s)."
            ))

    @transaction.atomic
    def _reconciliar(self, pub, solicitud):
        """Archiva la publicación y devuelve la propiedad a borrador.

        La propiedad queda en ``borrador`` porque su proceso no terminó; al
        publicarse de verdad, ``publicar_solicitud`` la vuelve a poner en
        ``publicada``.
        """
        pub.estado = "archivada"
        pub.save(update_fields=["estado", "updated_at"])

        propiedad = pub.propiedad
        if propiedad and not propiedad.tipo_cierre:
            # Si la propiedad ya se cerró (vendida/arrendada) no se toca: el
            # cierre manda sobre la vitrina.
            propiedad.estado = "borrador"
            propiedad.save(update_fields=["estado", "updated_at"])
