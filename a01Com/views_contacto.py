import json
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ConsultaContacto

logger = logging.getLogger(__name__)


@require_POST
@csrf_exempt
def enviar_consulta_email(request):
    """
    Recibe una consulta desde el botón de email del navbar.

    Crea un registro en ConsultaContacto (log de seguimiento) y envía el
    mensaje a contacto@serca.online.
    """
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        data = request.POST

    email = (data.get("email") or "").strip()
    telefono = (data.get("telefono") or "").strip()
    mensaje = (data.get("mensaje") or "").strip()

    if not email or not mensaje:
        return JsonResponse({"ok": False, "error": "Email y mensaje son obligatorios."}, status=400)

    if "@" not in email or "." not in email:
        return JsonResponse({"ok": False, "error": "Ingresa un email válido."}, status=400)

    consulta = ConsultaContacto.objects.create(
        email=email,
        telefono=telefono,
        mensaje=mensaje,
        estado="pendiente",
        creado_por=request.user if request.user.is_authenticated else None,
    )

    destino = getattr(settings, "CONTACTO_EMAIL", "contacto@serca.online")
    sitio = getattr(settings, "SITE_NAME", "Serca Propiedades")

    asunto = f"Consulta desde el sitio: {email}"
    cuerpo = (
        f"Nueva consulta recibida desde el formulario de contacto:\n\n"
        f"Email: {email}\n"
        f"Teléfono: {telefono or 'No indicado'}\n"
        f"Mensaje:\n{mensaje}\n\n"
        f"Registro #{consulta.id} - {sitio}"
    )

    try:
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destino],
            fail_silently=False,
        )
        logger.info(f"Consulta #{consulta.id} enviada a {destino} ({email})")
    except Exception as e:
        logger.error(f"Error enviando consulta #{consulta.id}: {e}", exc_info=True)
        # No rompemos: el registro queda en el log igualmente
        return JsonResponse({"ok": False, "error": "No se pudo enviar el correo en este momento. Inténtalo más tarde."}, status=500)

    return JsonResponse({"ok": True, "mensaje": "Gracias, recibimos tu consulta. Te responderemos a la brevedad."})
