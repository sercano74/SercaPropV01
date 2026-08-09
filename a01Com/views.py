from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings


def robots_txt(request):
    """robots.txt dinámico: indica sitemap y bloquea paneles internos."""
    dominio = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
    contenido = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /cuenta/\n"
        "Disallow: /api/\n"
        "Disallow: /gestion/\n"
        "Disallow: /accounts/\n"
        "Disallow: /perfil/\n\n"
        f"Sitemap: https://{dominio}/sitemap.xml\n"
    )
    return HttpResponse(contenido, content_type="text/plain")
from django.db.models import Q
from .models import Communication


@login_required
def centro_comunicaciones(request):
    """Centro de comunicaciones del usuario con filtros."""

    # ── Filtros desde GET ─────────────────────────────────────
    filtro_tipo = request.GET.get("tipo", "")
    filtro_propiedad = request.GET.get("propiedad", "")
    filtro_propietario = request.GET.get("propietario", "")
    filtro_comuna = request.GET.get("comuna", "")
    filtro_q = request.GET.get("q", "").strip()

    # ── Querysets base ────────────────────────────────────────
    recibidos = Communication.objects.filter(
        recipient=request.user, is_deleted=False
    ).select_related("emitter_user")

    enviados = Communication.objects.filter(
        emitter_user=request.user, is_deleted=False
    ).select_related("recipient")

    # ── Aplicar filtros ───────────────────────────────────────
    def apply_filters(qs, user_field):
        """Aplica filtros a un queryset de comunicaciones."""
        if filtro_tipo:
            qs = qs.filter(source_type=filtro_tipo)
        if filtro_propiedad:
            qs = qs.filter(property_id=filtro_propiedad)
        if filtro_q:
            qs = qs.filter(
                Q(title__icontains=filtro_q)
                | Q(message__icontains=filtro_q)
            )
        return qs

    recibidos = apply_filters(recibidos, "recipient")
    enviados = apply_filters(enviados, "emitter_user")

    no_leidos = recibidos.filter(is_read=False).count()

    # ── Datos para filtros ────────────────────────────────────
    from a03Prop.models import Propiedad
    from a00seg.models import Comuna

    # Propiedades relacionadas con el usuario (dueño o corredor)
    propiedades_usuario = Propiedad.objects.filter(
        Q(dueno=request.user)
        | Q(corredores__corredor=request.user)
    ).distinct().order_by("calle")[:100]

    todas_comunas = Comuna.objects.all().order_by("nombre")

    return render(request, "comunicaciones.html", {
        "recibidos": recibidos,
        "enviados": enviados,
        "no_leidos": no_leidos,
        "filtro_tipo": filtro_tipo,
        "filtro_propiedad": filtro_propiedad,
        "filtro_propietario": filtro_propietario,
        "filtro_comuna": filtro_comuna,
        "filtro_q": filtro_q,
        "propiedades_usuario": propiedades_usuario,
        "todas_comunas": todas_comunas,
    })


@login_required
def enviar_comunicacion(request):
    if request.method == "POST":
        from a00seg.models import User

        recipient_id = request.POST.get("recipient_id")
        title = request.POST.get("title")
        message = request.POST.get("message")

        recipient = get_object_or_404(User, id=recipient_id)

        Communication.objects.create(
            recipient=recipient,
            emitter_user=request.user,
            source_type=request.POST.get("source_type", "usuario_base"),
            title=title,
            message=message,
        )
        messages.success(request, "Mensaje enviado correctamente.")
        return redirect("centro_comunicaciones")

    from a00seg.models import User

    usuarios = User.objects.filter(is_active=True).exclude(id=request.user.id)
    return render(request, "enviar_comunicacion.html", {"usuarios": usuarios})


@login_required
def marcar_leido(request, com_id):
    com = get_object_or_404(Communication, id=com_id, recipient=request.user)
    com.is_read = True
    com.save()
    return redirect("centro_comunicaciones")


@login_required
def marcar_no_leido(request, com_id):
    """Toggle dual: desmarca como no leído."""
    com = get_object_or_404(Communication, id=com_id, recipient=request.user)
    if com.is_read:
        com.is_read = False
        com.save()
    else:
        com.is_read = True
        com.save()
    return redirect("centro_comunicaciones")


@login_required
def eliminar_comunicacion(request, com_id):
    com = get_object_or_404(Communication, id=com_id, recipient=request.user)
    com.is_deleted = True
    com.save()
    messages.success(request, "Mensaje eliminado.")
    return redirect("centro_comunicaciones")
