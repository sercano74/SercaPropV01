"""
Utilidades para confirmación de email.
Genera tokens seguros, envía correos de confirmación y verifica tokens.
"""
import os
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
import hashlib
import logging

logger = logging.getLogger(__name__)


class EmailConfirmationTokenGenerator(PasswordResetTokenGenerator):
    """Generador de tokens para confirmación de email.
    Hereda de PasswordResetTokenGenerator - la expiración default es
    PASSWORD_RESET_TIMEOUT (3 días por defecto).
    """
    key_salt = "a00seg.email_utils.EmailConfirmationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        """
        Hash que incluye user.pk, timestamp, email y email_confirmado.
        Al cambiar el email o confirmarlo, los tokens anteriores se invalidan.
        """
        return str(user.pk) + str(timestamp) + str(user.email) + str(user.email_confirmado)


# Instancia global para usar en vistas
email_token_generator = EmailConfirmationTokenGenerator()


def send_confirmation_email(user, request=None):
    """
    Envía el correo de confirmación al usuario.
    Retorna True si se envió correctamente, False en caso contrario.
    """
    try:
        token = email_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Construir URL absoluta de confirmación
        site_domain = getattr(settings, 'SITE_DOMAIN', None) or os.environ.get(
            'SITE_DOMAIN', 'propiedades.serca.online'
        )
        protocol = 'https'
        confirm_url = f"{protocol}://{site_domain}{reverse('confirmar_email', kwargs={'uidb64': uid, 'token': token})}"

        site_name = getattr(settings, 'SITE_NAME', 'Serca Propiedades')
        expiry_hours = getattr(settings, 'ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_HOURS', 48)

        subject = "Confirma tu correo electrónico - Serca Propiedades"

        html_message = render_to_string("email/confirmacion_email.html", {
            "user": user,
            "confirm_url": confirm_url,
            "site_name": site_name,
            "expiry_hours": expiry_hours,
        })

        text_message = f"""
Hola {user.get_full_name() or user.username},

Gracias por registrarte en Serca Propiedades.

Para confirmar tu correo electrónico, haz clic en el siguiente enlace:
{confirm_url}

Este enlace expirará en {expiry_hours} horas.

Si no creaste esta cuenta, puedes ignorar este mensaje.

Saludos,
El equipo de Serca Propiedades
        """

        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email de confirmación enviado a {user.email}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar email de confirmación a {user.email}: {e}")
        return False
