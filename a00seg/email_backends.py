"""
Backend de email para Resend usando su API HTTP (https://api.resend.com/emails).

¿Por qué API en vez de SMTP?
- El SMTP (smtp.resend.com:587) puede quedar colgado o bloqueado desde IPs de
  datacenter (Railway), provocando TimeoutError/WORKER TIMEOUT en gunicorn.
- La API HTTP (HTTPS/443) responde en milisegundos, funciona desde cualquier IP
  y es la vía recomendada por Resend para aplicaciones.

Configuración (variables de entorno):
    EMAIL_BACKEND = resend                       -> activa este backend
    RESEND_API_KEY = re_xxxxxxxxxxxx             -> API key de Resend
    EMAIL_DEFAULT_FROM = Nombre <correo@dominio> -> remitente (dominio verificado)
"""
import json
import logging
import urllib.request
import urllib.error

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class ResendAPIBackend(BaseEmailBackend):
    """Envía correos a través de la API REST de Resend."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        # Acepta la key por RESEND_API_KEY o EMAIL_HOST_PASSWORD (ambas definidas
        # en Railway apuntando a la key de Resend).
        self.api_key = (
            getattr(settings, "RESEND_API_KEY", "")
            or getattr(settings, "EMAIL_HOST_PASSWORD", "")
            or ""
        )
        self.from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")

    def send_messages(self, email_messages):
        if not self.api_key:
            logger.error("ResendAPIBackend: falta RESEND_API_KEY / EMAIL_HOST_PASSWORD.")
            if not self.fail_silently:
                raise ValueError("ResendAPIBackend: falta la API key de Resend.")
            return 0

        enviados = 0
        for message in email_messages:
            try:
                self._enviar_uno(message)
                enviados += 1
            except Exception as e:
                logger.error("ResendAPIBackend: error enviando email: %s", e)
                if not self.fail_silently:
                    raise
        return enviados

    def _enviar_uno(self, message):
        destinatarios = (
            list(message.to or [])
            + list(message.cc or [])
            + list(message.bcc or [])
        )
        email_from = message.from_email or self.from_email

        payload = {
            "from": email_from,
            "to": destinatarios,
            "subject": message.subject,
        }
        if message.body:
            payload["text"] = message.body
        html = None
        for contenido, mimetype in (message.alternatives or []):
            if mimetype == "text/html":
                html = contenido
        if html:
            payload["html"] = html
        elif getattr(message, "html", None):
            payload["html"] = message.html

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            RESEND_API_URL,
            data=data,
            method="POST",
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                # Cloudflare (usado por Resend) bloquea el User-Agent por
                # defecto de urllib (Python-urllib/3.x) con error 1010.
                "User-Agent": "SercaProp/1.0 (+https://propiedades.serca.online)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    raise RuntimeError("Resend API respondió status " + str(resp.status))
        except urllib.error.HTTPError as e:
            # Leer el cuerpo del error (contiene el motivo real: dominio no
            # verificado, key inválida, etc.)
            motivo = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
            raise RuntimeError("Resend API HTTP " + str(e.code) + ": " + motivo) from e
