"""Aviso al propietario de una publicación hecha en su representación.

Es el único correo de este flujo, y es deliberadamente uno solo: informa al
propietario de que su propiedad va a salir publicada, le da un enlace para
oponerse dentro del plazo, y deja copia oculta a la gerencia y a la
superadministración.

**Límite honesto:** el aviso va a un correo que proporciona el representante.
Si escribió el suyo, el propietario nunca se entera. Eso lo mitigan la
declaración jurada del formulario, esta copia oculta y el cotejo del correo
contra el mandato al aprobar el pago; ninguna de las tres lo garantiza, y así
debe entenderse.

``send_mail`` de Django no acepta ``bcc``, por eso aquí se usa
``EmailMultiAlternatives``.
"""

import logging
import secrets

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from a00seg.models import User

logger = logging.getLogger(__name__)

ROLES_COPIA = ("gerente", "superadmin")
LARGO_TOKEN = 32


def generar_token():
    """Token de un solo propósito: objetar o no objetar."""
    return secrets.token_urlsafe(LARGO_TOKEN)[:64]


def correos_de_copia():
    """Correos de gerentes y superadministradores activos, sin repetidos."""
    correos = (
        User.objects
        .filter(rol__in=ROLES_COPIA, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    vistos = []
    for correo in correos:
        if correo not in vistos:
            vistos.append(correo)
    return vistos


def dominio_publico():
    dominio = getattr(settings, "SITE_DOMAIN", "") or "propiedades.serca.online"
    return dominio.strip().strip("/")


def url_aviso(solicitud):
    """URL absoluta de la página pública de objeción."""
    ruta = reverse("aviso_representacion", kwargs={"token": solicitud.aviso_token})
    return f"https://{dominio_publico()}{ruta}"


def _contexto(solicitud):
    propiedad = solicitud.propiedad
    return {
        "solicitud": solicitud,
        "propiedad": propiedad,
        "propietario_nombre": propiedad.propietario_nombre if propiedad else "",
        "representante": solicitud.usuario.get_full_name() or solicitud.usuario.email,
        "tipo_mandato": solicitud.get_tipo_mandato_display(),
        "url_aviso": url_aviso(solicitud),
        "dias": solicitud.objecion_dias,
        "objecion_hasta": solicitud.objecion_hasta,
        "site_name": getattr(settings, "SITE_NAME", "Serca Propiedades"),
    }


def enviar_aviso_propietario(solicitud):
    """Envía el aviso. Devuelve ``(ok, detalle)``.

    No levanta la excepción hacia arriba: si el correo falla, la solicitud
    igual debe quedar aprobada. El fallo se registra en el log. Es una decisión
    deliberada: bloquear el flujo por un problema de correo deja al gerente sin
    poder trabajar, y el aviso puede reenviarse.
    """
    propiedad = solicitud.propiedad
    destino = (propiedad.propietario_email if propiedad else "") or ""
    if not destino:
        return False, "La propiedad no tiene correo del propietario."

    if not solicitud.aviso_token:
        solicitud.aviso_token = generar_token()

    contexto = _contexto(solicitud)
    asunto = (
        f"Aviso de publicación: {propiedad.get_tipo_prop_display()} en "
        f"{propiedad.comuna or 'su comuna'}"
    )

    try:
        html = render_to_string("email/aviso_representacion.html", contexto)
        texto = render_to_string("email/aviso_representacion.txt", contexto)
    except Exception as e:
        logger.error("Aviso al propietario: error renderizando plantillas: %s", e)
        return False, f"Error de plantilla: {e}"

    mensaje = EmailMultiAlternatives(
        subject=asunto,
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destino],
        bcc=correos_de_copia(),
    )
    mensaje.attach_alternative(html, "text/html")

    try:
        mensaje.send(fail_silently=False)
    except Exception as e:
        logger.error(
            "Aviso al propietario: fallo el envío a %s: %s", destino, e
        )
        return False, f"{type(e).__name__}: {e}"

    logger.info("Aviso al propietario enviado a %s (solicitud #%s)", destino, solicitud.id)
    return True, None
