"""Reglas de visibilidad de una publicación en la vitrina.

Una propiedad sólo debe aparecer en el home —y en el buscador, las landing
pages y el sitemap— cuando su proceso de publicación terminó de verdad.

El proceso de cinco etapas vive en ``SolicitudPublicacion``; la ficha que se
muestra en la vitrina vive en ``PublicacionProp``. Son dos objetos distintos
y, si nada los mantiene sincronizados, una propiedad puede quedar a la vista
con su proceso todavía a medio camino. Es exactamente lo que ocurría con las
propiedades 8 y 9: aparecían en el home mientras su solicitud seguía en el
paso 3 (el responsable todavía no subía la Orden de Gestión y, en
representación, tampoco había mandato).

Este módulo concentra la regla en un solo lugar para que las superficies que
muestran propiedades no vuelvan a divergir. La regla es una sola:

    una propiedad se muestra si no tiene proceso en curso, o si el proceso
    en curso ya llegó al estado ``publicada``.

Un proceso "caído" (rechazado o cancelado) ya no gobierna la visibilidad: no
hay etapas pendientes que exigir, así que la propiedad se rige por lo que
diga su ``PublicacionProp``.
"""

ESTADO_PUBLICADA = "publicada"

# Estados terminales que ya no exigen etapas nuevas.
ESTADOS_CAIDAS = ("rechazada", "cancelada")

# Estados de la solicitud que aún no han llegado a publicar.
ESTADOS_INCONCLUSOS = (
    "pago_revision",
    "pago_objetado",
    "pago_aprobado",
    "esperando_corredor",
    "en_revision_corredor",
    "og_pendiente",
    "og_aceptada",
    "en_validacion",
    "objetada",
)


def _solicitud_model():
    """Import perezoso: evita ciclos con ``models``."""
    from .models import SolicitudPublicacion
    return SolicitudPublicacion


def solicitud_activa(propiedad):
    """La solicitud en curso de ``propiedad``, o ``None``.

    Se excluyen las caídas: una solicitud rechazada o cancelada ya no manda.
    """
    if propiedad is None or not getattr(propiedad, "pk", None):
        return None
    return (
        _solicitud_model().objects
        .filter(propiedad=propiedad)
        .exclude(estado__in=ESTADOS_CAIDAS)
        .order_by("-created_at")
        .first()
    )


def proceso_completo(propiedad):
    """``True`` si la propiedad puede mostrarse según su proceso.

    Sin solicitud (publicación anterior al flujo de cinco pasos) o con la
    solicitud ya publicada, no hay etapas pendientes que exigir.
    """
    solicitud = solicitud_activa(propiedad)
    return solicitud is None or solicitud.estado == ESTADO_PUBLICADA


def ids_con_proceso_inconcluso():
    """IDs de propiedades con una solicitud a medio camino.

    Es un ``values_list`` para poder usarlo como subconsulta en un
    ``exclude()``. Si una propiedad tuviera varias solicitudes y alguna ya
    publicó, no debe aparecer aquí, así que se filtra por la más reciente
    excluyendo caídas.
    """
    modelo = _solicitud_model()
    recientes = {}
    for propiedad_id, estado in (
        modelo.objects
        .exclude(propiedad__isnull=True)
        .exclude(estado__in=ESTADOS_CAIDAS)
        .order_by("propiedad_id", "-created_at")
        .values_list("propiedad_id", "estado")
    ):
        # El orden por -created_at deja primero la más reciente de cada
        # propiedad; el resto se descarta.
        recientes.setdefault(propiedad_id, estado)

    return [
        propiedad_id
        for propiedad_id, estado in recientes.items()
        if estado != ESTADO_PUBLICADA
    ]


def publicaciones_visibles(queryset=None):
    """Publicaciones en estado ``publicada`` cuya propiedad puede mostrarse.

    ``queryset`` permite partir de un conjunto ya filtrado (por destacada, por
    comuna, etc.); si se omite, parte de todas las ``PublicacionProp``.
    """
    from .models import PublicacionProp
    base = queryset if queryset is not None else PublicacionProp.objects.all()
    return base.filter(estado=ESTADO_PUBLICADA).exclude(
        propiedad_id__in=ids_con_proceso_inconcluso()
    )


def faltantes_para_publicar(solicitud):
    """Etapas que aún no se cumplen para poder publicar ``solicitud``.

    Devuelve una lista de textos para el mensaje de error. La usan la vista de
    publicación y las pruebas: es la definición única de "todas las etapas".
    """
    faltantes = []

    if solicitud.corredor_asignado_id is None:
        faltantes.append("un responsable asignado")

    if not solicitud.orden_gestion or not solicitud.og_aceptada:
        faltantes.append("la Orden de Gestión aprobada por la gerencia")

    if (
        solicitud.tipo_publicante == "representante"
        and not solicitud.mandato_archivo
    ):
        faltantes.append("el mandato del propietario")

    return faltantes
