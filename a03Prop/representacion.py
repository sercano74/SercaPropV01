"""Publicación en representación: permisos, cupo mensual y datos del propietario.

El propietario no entra a la plataforma. Quien publica es un corredor, gerente o
superadministrador que ocupa el casillero de ``SolicitudPublicacion.usuario``.
Este módulo concentra las tres reglas que gobiernan ese caso:

1. **Quién puede representar.** Corredor con suscripción vigente y plan que lo
   habilite; gerente y superadministrador, siempre.
2. **Cuántas publicaciones por mes.** Cupo del plan, por mes calendario. Cuenta
   la producción total del corredor, propia o en representación.
3. **Qué datos del propietario se aceptan.** Se validan en el servidor, con
   límites de longitud y tipo, porque el JavaScript del formulario es comodidad
   y no una frontera de seguridad.
"""

import unicodedata

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from .models import SolicitudPublicacion

ROLES_GERENCIA = ("gerente", "superadmin")

# Sólo la gerencia puede invocar un mandato verbal: es el que no deja rastro.
MANDATOS_RESTRINGIDOS = ("verbal",)

MANDATOS_VALIDOS = ("verbal", "escrito", "notarial")

LARGO_MAXIMO = {
    "propietario_nombre": 255,
    "propietario_dni": 20,
    "propietario_email": 254,
    "propietario_celular": 20,
}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def es_gerencia(user):
    """``True`` para gerente y superadministrador."""
    return bool(user and getattr(user, "rol", "") in ROLES_GERENCIA)


def nombre_mes(numero):
    if 1 <= numero <= 12:
        return MESES[numero - 1]
    return ""


def _limpiar(valor):
    """Normaliza un texto de formulario: sin espacios sobrantes ni controles."""
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKC", str(valor))
    return " ".join(texto.split())


def suscripcion_vigente(user):
    """La suscripción del corredor si está activa y no vencida."""
    suscripcion = getattr(user, "suscripcion", None)
    if not suscripcion:
        return None
    if not suscripcion.activa or not suscripcion.plan:
        return None
    if suscripcion.fecha_fin and suscripcion.fecha_fin <= timezone.now():
        return None
    return suscripcion


def puede_representar(user):
    """``(permitido, mensaje)``.

    El mensaje viene listo para mostrar cuando no se permite, porque cada
    motivo pide una acción distinta del usuario.
    """
    if es_gerencia(user):
        return True, ""

    suscripcion = suscripcion_vigente(user)
    if not suscripcion:
        return False, (
            "Necesitas una suscripción vigente para publicar en representación "
            "de un propietario. Revísala en tu perfil."
        )
    if not suscripcion.plan.permite_representacion:
        return False, (
            f"Tu plan {suscripcion.plan.nombre} no permite publicar en "
            "representación de terceros. Escríbenos si quieres habilitarlo."
        )
    return True, ""


def publicaciones_del_mes(user, hoy=None):
    """Solicitudes creadas por ``user`` este mes, sin contar las caídas."""
    hoy = hoy or timezone.localtime()
    inicio = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        SolicitudPublicacion.objects
        .filter(usuario=user, created_at__gte=inicio)
        .exclude(estado__in=["rechazada", "cancelada"])
        .count()
    )


def cupo_del_mes(user, hoy=None):
    """``(usadas, limite)``. ``limite`` es ``None`` cuando no hay tope."""
    if es_gerencia(user):
        return 0, None
    suscripcion = suscripcion_vigente(user)
    if not suscripcion:
        return 0, 0
    return publicaciones_del_mes(user, hoy), suscripcion.plan.max_publicaciones_mensual


def puede_crear_publicacion(user, hoy=None):
    """``(permitido, mensaje)`` sobre el cupo mensual del plan."""
    usadas, limite = cupo_del_mes(user, hoy)
    if limite is None:
        return True, ""
    if limite and usadas >= limite:
        hoy = hoy or timezone.localtime()
        siguiente_mes = 1 if hoy.month == 12 else hoy.month + 1
        return False, (
            f"Tu plan permite {limite} publicaciones por mes y ya usaste {usadas}. "
            f"Podrás publicar nuevamente en {nombre_mes(siguiente_mes)}."
        )
    return True, ""


def _validar_texto(campo, valor, obligatorio=True):
    """Valida longitud y presencia. Devuelve el mensaje de error o ``''``."""
    limite = LARGO_MAXIMO.get(campo, 255)
    if not valor:
        return "Completa este dato del propietario." if obligatorio else ""
    if len(valor) > limite:
        return f"No puede superar los {limite} caracteres."
    return ""


def procesar_datos_propietario(post, files, user):
    """Extrae y valida los datos del propietario.

    Devuelve ``(datos, errores)``. ``datos`` trae sólo lo validado; si hay
    errores, la vista no debe crear nada y debe repoblar el formulario.

    Un POST puede traer estos campos aunque el selector diga "propietario".
    La vista llama a esta función **sólo** cuando el selector dice
    "representante", así que un envío cruzado no llega hasta aquí.
    """
    datos = {
        "propietario_nombre": _limpiar(post.get("propietario_nombre")),
        "propietario_dni": _limpiar(post.get("propietario_dni")),
        "propietario_email": _limpiar(post.get("propietario_email")),
        "propietario_celular": _limpiar(post.get("propietario_celular")),
        "tipo_mandato": _limpiar(post.get("tipo_mandato")),
    }
    errores = []

    for campo in ("propietario_nombre", "propietario_dni", "propietario_email"):
        error = _validar_texto(campo, datos[campo])
        if error:
            errores.append(f"Propietario: {error}")

    error_celular = _validar_texto(
        "propietario_celular", datos["propietario_celular"], obligatorio=False
    )
    if error_celular:
        errores.append(f"Teléfono del propietario: {error_celular}")

    if datos["propietario_email"]:
        try:
            validate_email(datos["propietario_email"])
        except ValidationError:
            errores.append("El correo del propietario no tiene un formato válido.")

    if datos["tipo_mandato"] not in MANDATOS_VALIDOS:
        errores.append("Selecciona el tipo de mandato del propietario.")
    elif (
        datos["tipo_mandato"] in MANDATOS_RESTRINGIDOS
        and not es_gerencia(user)
    ):
        errores.append(
            "El mandato verbal sólo lo puede declarar la gerencia. Sube el "
            "mandato escrito o notarial."
        )

    # El mandato verbal no tiene archivo: exigirlo dejaría la vía verbal
    # inutilizable. Sólo la gerencia puede declararlo (validado arriba), así que
    # aquí basta con no pedir el archivo en ese caso.
    mandato = files.get("mandato_archivo") if files else None
    verbal_de_gerencia = (
        datos["tipo_mandato"] == "verbal" and es_gerencia(user)
    )
    if not mandato and not verbal_de_gerencia:
        errores.append("Debes adjuntar el mandato firmado por el propietario.")
    datos["mandato_archivo"] = mandato

    if post.get("declara_mandato") != "1":
        errores.append(
            "Debes declarar que el correo indicado pertenece al propietario y "
            "que cuentas con su mandato para publicar."
        )

    return datos, errores


def etiqueta_representacion(solicitud):
    """Texto corto para listados y detalle."""
    if solicitud.tipo_publicante != SolicitudPublicacion.TipoPublicante.REPRESENTANTE:
        return ""
    propiedad = solicitud.propiedad
    nombre = propiedad.propietario_nombre if propiedad else ""
    return f"En representación de {nombre}" if nombre else "En representación"
