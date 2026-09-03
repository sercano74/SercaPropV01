import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ConsultaContacto, Communication, SourceTypeChoices

logger = logging.getLogger(__name__)


def _equipo_consultas():
    """Usuarios que gestionan consultas (gerente y superadmin)."""
    from a00seg.models import User
    return User.objects.filter(is_active=True, rol__in=["gerente", "superadmin"])


def _avisar_cdc(consulta, emisor):
    """Crea una Communication en el CDC del equipo para la nueva consulta."""
    equipo = _equipo_consultas().exclude(id=emisor.id) if emisor else _equipo_consultas()
    for user in equipo:
        Communication.objects.create(
            recipient=user,
            emitter_user=emisor,
            source_type=SourceTypeChoices.SISTEMA,
            title=f"📧 Nueva consulta: {consulta.email}",
            message=(
                f"Teléfono: {consulta.telefono or 'No indicado'}\n\n"
                f"Consulta #{consulta.id}\n\n{consulta.mensaje}"
            ),
            related_object_id=consulta.id,
            related_object_type="consulta",
        )


def _avisar_cdc_respuesta(consulta, emisor, respuesta):
    """Crea una Communication en el CDC del equipo al responder una consulta."""
    for user in _equipo_consultas():
        Communication.objects.create(
            recipient=user,
            emitter_user=emisor,
            source_type=SourceTypeChoices.SISTEMA,
            title=f"📤 Respuesta a consulta #{consulta.id}",
            message=(
                f"Se respondió la consulta #{consulta.id} de {consulta.email}.\n\n"
                f"Respuesta:\n{respuesta}"
            ),
            related_object_id=consulta.id,
            related_object_type="consulta",
        )


@require_POST
@csrf_exempt
def enviar_consulta_email(request):
    """
    Recibe una consulta desde el botón de email del navbar.

    Crea un registro en ConsultaContacto (log de seguimiento), avisa al CDC
    del equipo y envía el mensaje a contacto@serca.online.
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

    send_ok = True
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
        send_ok = False

    # Avisar al CDC del equipo, siempre que haya un emisor disponible.
    emisor = consulta.creado_por
    if emisor is None:
        emisor = _equipo_consultas().order_by("id").first()
    if emisor is not None:
        try:
            _avisar_cdc(consulta, emisor)
        except Exception as e:
            logger.error(f"No se pudo avisar al CDC de la consulta #{consulta.id}: {e}", exc_info=True)

    if not send_ok:
        return JsonResponse(
            {"ok": False, "error": "No se pudo enviar el correo en este momento, pero tu consulta quedó registrada. Te contactaremos a la brevedad."},
            status=500,
        )

    return JsonResponse({"ok": True, "mensaje": "Gracias, recibimos tu consulta. Te responderemos a la brevedad."})


@login_required
def gestion_consultas(request):
    """Listado de consultas del log (embudo), solo para gerente/superadmin."""
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos para ver las consultas.")
        return redirect("home")

    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")

    consultas = ConsultaContacto.objects.select_related("creado_por")
    if q:
        consultas = consultas.filter(
            Q(email__icontains=q) | Q(telefono__icontains=q) | Q(mensaje__icontains=q)
        )
    if estado:
        consultas = consultas.filter(estado=estado)

    conteo = {
        "pendiente": ConsultaContacto.objects.filter(estado="pendiente").count(),
        "respondida": ConsultaContacto.objects.filter(estado="respondida").count(),
        "cerrada": ConsultaContacto.objects.filter(estado="cerrada").count(),
    }

    return render(request, "gestion_consultas.html", {
        "consultas": consultas,
        "q": q,
        "estado": estado,
        "conteo": conteo,
    })


@login_required
def detalle_consulta(request, consulta_id):
    """Detalle de una consulta del log."""
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos para ver las consultas.")
        return redirect("home")
    consulta = get_object_or_404(ConsultaContacto, id=consulta_id)
    return render(request, "detalle_consulta.html", {"consulta": consulta})


@login_required
def responder_consulta(request, consulta_id):
    """Registra la respuesta, la envía al consultante y avisa al CDC."""
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos para gestionar consultas.")
        return redirect("home")
    consulta = get_object_or_404(ConsultaContacto, id=consulta_id)
    if request.method == "POST":
        respuesta = (request.POST.get("respuesta") or "").strip()
        nuevo_estado = request.POST.get("estado", "")
        if not respuesta:
            messages.error(request, "Escribe una respuesta antes de guardar.")
            return redirect("detalle_consulta", consulta_id=consulta.id)
        consulta.respuesta = respuesta
        if nuevo_estado in ("pendiente", "respondida", "cerrada"):
            consulta.estado = nuevo_estado
        if consulta.estado != "pendiente":
            consulta.respondido_at = timezone.now()
        consulta.save()

        # Enviar la respuesta al email del consultante
        sitio = getattr(settings, "SITE_NAME", "Serca Propiedades")
        asunto = f"Tu consulta en {sitio} (#{consulta.id})"
        cuerpo = (
            f"Hola,\n\nGracias por tu consulta en {sitio}. Esta es nuestra respuesta:\n\n"
            f"{respuesta}\n\n"
            f"Saludos,\n{sitio}"
        )
        try:
            send_mail(
                subject=asunto,
                message=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[consulta.email],
                fail_silently=False,
            )
            logger.info(f"Respuesta a consulta #{consulta.id} enviada a {consulta.email}")
        except Exception as e:
            logger.error(f"Error enviando respuesta a consulta #{consulta.id}: {e}", exc_info=True)
            messages.warning(request, "Se guardó la respuesta, pero no se pudo enviar el correo al consultante.")

        # Avisar al CDC del equipo sobre la respuesta
        try:
            _avisar_cdc_respuesta(consulta, request.user, respuesta)
        except Exception as e:
            logger.error(f"No se pudo avisar al CDC de la respuesta #{consulta.id}: {e}", exc_info=True)

        messages.success(request, "Consulta respondida: se envió el correo al consultante y se avisó al CDC.")
        return redirect("detalle_consulta", consulta_id=consulta.id)
    return redirect("detalle_consulta", consulta_id=consulta.id)
