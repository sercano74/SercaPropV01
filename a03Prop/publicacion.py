"""Reglas de la vitrina y del proceso de publicación.

Hay dos objetos que dicen cosas distintas sobre una propiedad:

* ``SolicitudPublicacion`` — el proceso de cinco etapas que lleva a publicar.
* ``PublicacionProp`` — la ficha que efectivamente se muestra en la vitrina.

Reparto de responsabilidades
----------------------------
El proceso gobierna **el acto de publicar**: ``publicar_solicitud`` y
``aprobar_publicacion`` no dejan publicar si faltan etapas (responsable,
Orden de Gestión aprobada, mandato en representación). Para eso está
``faltantes_para_publicar``.

Una vez publicada, la vitrina se rige por la ``PublicacionProp``: si está en
estado ``publicada`` y vigente, se muestra. **El proceso no despublica.** Si
un trámite posterior —una renovación, un segundo intento, una solicitud
abierta por cualquier motivo— pudiera ocultar la ficha, una propiedad pagada
y accesible por su URL desaparecería del home, del buscador y del sitemap sin
que nadie lo hubiera decidido.

Las incoherencias reales —una publicación marcada como publicada sin haber
cumplido nunca las etapas— se corrigen con
``python manage.py reconciliar_publicaciones``, que archiva la publicación y
devuelve la propiedad a borrador. Esa decisión se toma a conciencia; la
vitrina no la adivina.
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
    """Publicaciones en estado ``publicada``.

    ``queryset`` permite partir de un conjunto ya filtrado (por destacada, por
    comuna, por vigencia, etc.); si se omite, parte de todas las
    ``PublicacionProp``.

    No se filtra por el proceso de cinco etapas a propósito: una publicación
    ya publicada y vigente sigue en la vitrina aunque tenga una solicitud
    posterior abierta. Ocultarla vaciaba el home de propiedades que el cliente
    ya había pagado y que seguían accesibles por su ficha.
    """
    from .models import PublicacionProp
    base = queryset if queryset is not None else PublicacionProp.objects.all()
    return base.filter(estado=ESTADO_PUBLICADA)


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
