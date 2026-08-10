import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    CategoriaServicio,
    ServicioPublicitario,
    MensajeServicio,
    PagoServicio,
    CasoExito,
    ConfiguracionPrecioServicio,
    RatingServicio,
)
from a00seg.models import User
from a01Com.models import Communication, SourceTypeChoices

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

def _get_config_precios():
    """Obtiene la configuración de precios activa o valores por defecto."""
    config = ConfiguracionPrecioServicio.objects.filter(activo=True).first()
    if config:
        return config
    # Fallback a defaults si no hay config
    from types import SimpleNamespace
    return SimpleNamespace(
        valor_mensual=4200,
        valor_anual=39800,
        iva=0.19,
    )

def _calcular_pago(tipo_plan):
    """Calcula monto base, IVA y total según el tipo de plan desde DB."""
    config = _get_config_precios()
    if tipo_plan == "anual":
        base = config.valor_anual
    else:
        base = config.valor_mensual
    iva = round(base * float(config.iva))
    total = base + iva
    return base, iva, total


def _notificar(recipient, emitter, source_type, title, message, related_object_id=None, related_object_type=""):
    """Crea una notificación en el Centro de Comunicaciones.

    related_object_type permite al template saber a qué vista apuntar:
    - 'servicio'  -> detalle de revisión de servicio (a07serv)
    - 'solicitud' -> detalle de solicitud de publicación (a03Prop, default)
    """
    return Communication.objects.create(
        recipient=recipient,
        emitter_user=emitter,
        source_type=source_type,
        title=title,
        message=message,
        related_object_id=related_object_id,
        related_object_type=related_object_type,
    )


def _aprobar_publicacion_servicio(request, servicio):
    """Aprobar e iniciar la publicación: estado activo + fechas + notificaciones."""
    if request.user.rol not in ("gerente", "superadmin"):
        return False, "No tienes permisos para publicar servicios."
    if servicio.estado not in ("en_revision", "objetado"):
        return False, "Este servicio no está pendiente de publicación."

    meses = 12 if servicio.tipo_plan == "anual" else 1
    servicio.estado = "activo"
    servicio.fecha_inicio = timezone.now()
    servicio.fecha_expiracion = timezone.now() + timedelta(days=30 * meses)
    servicio.revisado_por = request.user
    servicio.save()

    # Aprobar pagos pendientes del servicio
    PagoServicio.objects.filter(
        servicio=servicio, estado="pendiente"
    ).update(estado="aprobado", revisado_por=request.user)

    publicante_nombre = servicio.publicante.get_full_name() or servicio.publicante.email

    _notificar(
        recipient=servicio.publicante,
        emitter=request.user,
        source_type=SourceTypeChoices.GERENTE,
        title="✅ Tu servicio fue aprobado y publicado",
        message=(
            f"¡Buenas noticias! El servicio '{servicio.titulo}' fue revisado y aprobado. "
            f"Ya está visible en el directorio de Dato Constructor y publicado hasta el "
            f"{servicio.fecha_expiracion.strftime('%d/%m/%Y')}."
        ),
        related_object_id=servicio.id,
        related_object_type="servicio",
    )
    _enviar_email_servicio(
        "email/servicio_email.html",
        "Tu servicio fue publicado - Dato Constructor",
        servicio.publicante.email,
        {
            "tipo_aviso": "servicio_publicado",
            "titulo": "✅ Tu servicio ha sido publicado",
            "mensaje_plano": (
                f"¡Buenas noticias {publicante_nombre}! El servicio '{servicio.titulo}' "
                f"fue revisado y aprobado. Ya está visible en el directorio de Dato Constructor "
                f"y publicado hasta el {servicio.fecha_expiracion.strftime('%d/%m/%Y')}."
            ),
            "servicio": servicio,
            "publicante_nombre": publicante_nombre,
            "fecha_expiracion": servicio.fecha_expiracion.strftime("%d/%m/%Y"),
        },
    )

    return True, (
        f"✅ Servicio '{servicio.titulo}' aprobado y publicado hasta el "
        f"{servicio.fecha_expiracion.strftime('%d/%m/%Y')}. El publicante fue notificado."
    )


def _objetar_publicacion_servicio(request, servicio, razon):
    """Discrepancia en contenido o pago: estado objetado + motivo + notificaciones."""
    if request.user.rol not in ("gerente", "superadmin"):
        return False, "No tienes permisos para objetar servicios."
    if servicio.estado != "en_revision":
        return False, "Este servicio no está en revisión."

    razon = (razon or "").strip()
    if not razon:
        return False, "Debes indicar el motivo de la objeción."

    servicio.estado = "objetado"
    servicio.observaciones_admin = razon
    servicio.revisado_por = request.user
    servicio.save()

    publicante_nombre = servicio.publicante.get_full_name() or servicio.publicante.email

    _notificar(
        recipient=servicio.publicante,
        emitter=request.user,
        source_type=SourceTypeChoices.GERENTE,
        title="❌ Tu servicio fue objetado",
        message=(
            f"El servicio '{servicio.titulo}' presenta una discrepancia y NO fue publicado.\n\n"
            f"Motivo: {razon}\n\n"
            f"Por favor corrige la información o contacta a administración. "
            f"Una vez corregido, se puede solicitar una nueva revisión."
        ),
        related_object_id=servicio.id,
        related_object_type="servicio",
    )
    _enviar_email_servicio(
        "email/servicio_email.html",
        "Tu servicio fue objetado - Dato Constructor",
        servicio.publicante.email,
        {
            "tipo_aviso": "servicio_objetado",
            "titulo": "❌ Tu servicio fue objetado",
            "mensaje_plano": (
                f"Hola {publicante_nombre}, el servicio '{servicio.titulo}' presenta una "
                f"discrepancia y NO fue publicado.\n\nMotivo: {razon}\n\n"
                f"Corrige la información o contacta a administración. "
                f"Una vez corregido, se puede solicitar una nueva revisión."
            ),
            "servicio": servicio,
            "publicante_nombre": publicante_nombre,
            "razon": razon,
        },
    )

    return True, f"❌ Servicio '{servicio.titulo}' objetado. El publicante fue notificado."


def _reenviar_revision_servicio(servicio):
    """Reenviar un servicio objetado a revisión (el publicante corrigió)."""
    if servicio.estado != "objetado":
        return False, "Este servicio no está objetado."

    servicio.estado = "en_revision"
    servicio.observaciones_admin = ""
    servicio.save()
    return True, f"✅ Servicio '{servicio.titulo}' reenviado a revisión."


def _agrupar_hilos_servicio(servicio, user):
    """Agrupa los mensajes de un servicio en hilos de conversación.

    - Publicante: ve TODOS los hilos (un hilo por interesado), anónimos o no.
    - Usuario autenticado: ve solo los hilos donde él es remitente
      (o donde su email coincide con un mensaje anónimo suyo).
    - Visitante anónimo: no ve ningún hilo.

    Cada hilo trae:
      nombre / email / telefono: datos del interesado (usados como encabezado).
      remitente_id: id de usuario del interesado (None si es anónimo).
      mensajes: lista ordenada de menor a mayor fecha (orden de la conversación).
      mensajes_no_leidos, ultimo_mensaje, ultima_fecha: para la previsualización.
    """
    mensajes = list(
        servicio.mensajes.select_related("remitente", "destinatario").order_by("created_at")
    )

    es_publicante = user.is_authenticated and servicio.publicante_id == user.id

    hilos_map = {}
    if es_publicante:
        for m in mensajes:
            if m.remitente_id:
                clave = f"user:{m.remitente_id}"
            else:
                clave = f"anon:{m.email_remitente.lower()}"
            hilo = hilos_map.setdefault(clave, {
                "nombre": m.nombre_remitente,
                "email": m.email_remitente,
                "telefono": m.telefono_remitente,
                "remitente_id": m.remitente_id,
                "mensajes": [],
            })
            hilo["mensajes"].append(m)
    elif user.is_authenticated:
        email_user = (user.email or "").strip().lower()
        for m in mensajes:
            es_propio = (
                m.remitente_id == user.id
                or (m.remitente_id is None and m.email_remitente.lower() == email_user)
            )
            if not es_propio:
                continue
            hilo = hilos_map.setdefault("yo", {
                "nombre": user.get_full_name() or user.email,
                "email": user.email,
                "telefono": user.cel_phone or "",
                "remitente_id": user.id,
                "mensajes": [],
            })
            hilo["mensajes"].append(m)

    hilos = []
    for h in hilos_map.values():
        h["mensajes_no_leidos"] = sum(1 for m in h["mensajes"] if not m.is_leido)
        ultimo = h["mensajes"][-1] if h["mensajes"] else None
        h["ultimo_mensaje"] = ultimo.mensaje if ultimo else ""
        h["ultima_fecha"] = ultimo.created_at if ultimo else None
        hilos.append(h)

    # Hilos con actividad más reciente primero
    hilos.sort(key=lambda h: h["ultima_fecha"] or timezone.now(), reverse=True)
    return hilos


# ─────────────────────────────────────────────────────────
# VISTAS PÚBLICAS (Directorio de Servicios)
# ─────────────────────────────────────────────────────────

def lista_servicios(request):
    """Directorio público de servicios de construcción."""
    categorias = CategoriaServicio.objects.filter(is_active=True)

    # Filtros
    categoria_id = request.GET.get("categoria")
    search = request.GET.get("q")

    servicios = ServicioPublicitario.objects.filter(
        estado="activo",
        fecha_expiracion__gte=timezone.now(),
    ).select_related("categoria", "publicante")

    if categoria_id:
        servicios = servicios.filter(categoria_id=categoria_id)
    if search:
        servicios = servicios.filter(
            Q(titulo__icontains=search) |
            Q(descripcion__icontains=search) |
            Q(publicante__first_name__icontains=search) |
            Q(publicante__last_name__icontains=search)
        )

    servicios = servicios.order_by("-created_at")

    return render(request, "servicios/lista_servicios.html", {
        "servicios": servicios,
        "categorias": categorias,
        "filtro_categoria": categoria_id,
        "filtro_search": search,
    })


def detalle_servicio(request, servicio_id):
    """Detalle público de un servicio."""
    servicio = get_object_or_404(
        ServicioPublicitario.objects.select_related("categoria", "publicante"),
        id=servicio_id,
        estado="activo",
    )

    casos_exito = servicio.casos_exito.filter(is_publicado=True)
    ratings = servicio.ratings.all().select_related("usuario")

    # Pre-poblar datos si el usuario está autenticado
    datos_contacto = {}
    if request.user.is_authenticated:
        datos_contacto = {
            "nombre": request.user.get_full_name() or "",
            "email": request.user.email,
            "telefono": request.user.cel_phone or "",
        }

    # Solo publicante, gerente o superadmin pueden editar la imagen desde el detalle
    puede_editar_imagen = (
        request.user.is_authenticated
        and (
            request.user.rol in ("gerente", "superadmin")
            or servicio.publicante_id == request.user.id
        )
    )

    es_publicante = request.user.is_authenticated and servicio.publicante_id == request.user.id
    hilos = _agrupar_hilos_servicio(servicio, request.user)

    return render(request, "servicios/detalle_servicio.html", {
        "servicio": servicio,
        "casos_exito": casos_exito,
        "ratings": ratings,
        "datos_contacto": datos_contacto,
        "puede_editar_imagen": puede_editar_imagen,
        "es_publicante": es_publicante,
        "hilos": hilos,
    })


# ─────────────────────────────────────────────────────────
# ENVÍO DE MENSAJE AL PUBLICANTE
# ─────────────────────────────────────────────────────────

@login_required
def enviar_mensaje_servicio(request, servicio_id):
    """Usuario AUTENTICADO envía un mensaje al publicante del servicio.

    Los visitantes anónimos no pueden enviar mensajes: el decorador
    @login_required los redirige a la pantalla de inicio de sesión.
    Los datos de contacto se toman de la cuenta del usuario (no de los
    campos del formulario) para evitar suplantación de identidad.
    """
    servicio = get_object_or_404(ServicioPublicitario, id=servicio_id, estado="activo")

    if request.method == "POST":
        mensaje_texto = request.POST.get("mensaje", "").strip()

        if not mensaje_texto:
            messages.error(request, "Debes escribir el detalle de tu requerimiento.")
            return redirect("detalle_servicio", servicio_id=servicio.id)

        nombre = request.user.get_full_name() or request.user.email
        email = request.user.email or ""
        telefono = request.user.cel_phone or ""

        MensajeServicio.objects.create(
            servicio=servicio,
            remitente=request.user,
            destinatario=servicio.publicante,
            nombre_remitente=nombre,
            email_remitente=email,
            telefono_remitente=telefono,
            mensaje=mensaje_texto,
        )

        # Notificar al publicante
        _notificar(
            recipient=servicio.publicante,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title=f"Nuevo mensaje sobre: {servicio.titulo}",
            message=f"{nombre} ({email}, {telefono}) ha enviado un mensaje sobre tu servicio '{servicio.titulo}':\n{mensaje_texto[:300]}",
            related_object_id=servicio.id,
        )

        messages.success(
            request,
            "✅ Mensaje enviado correctamente. El prestador del servicio te contactará pronto."
        )
        return redirect("detalle_servicio", servicio_id=servicio.id)

    return redirect("detalle_servicio", servicio_id=servicio.id)


@login_required
def responder_mensaje_servicio(request, servicio_id, mensaje_id):
    """El publicante responde un mensaje desde el detalle del servicio."""
    servicio = get_object_or_404(
        ServicioPublicitario,
        id=servicio_id,
        publicante=request.user,
    )
    mensaje = get_object_or_404(MensajeServicio, id=mensaje_id, servicio=servicio)

    if request.method == "POST":
        respuesta = request.POST.get("respuesta", "").strip()
        if not respuesta:
            messages.error(request, "Debes escribir una respuesta.")
            return redirect("detalle_servicio", servicio_id=servicio.id)

        mensaje.respuesta = respuesta
        mensaje.respondido_at = timezone.now()
        mensaje.is_leido = True
        mensaje.leido_at = mensaje.leido_at or timezone.now()
        mensaje.save()

        # Notificar al interesado si es un usuario autenticado
        if mensaje.remitente_id and mensaje.remitente_id != request.user.id:
            _notificar(
                recipient=mensaje.remitente,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title=f"Respuesta sobre: {servicio.titulo}",
                message=(
                    f"{request.user.get_full_name() or request.user.email} respondió a tu "
                    f"consulta sobre '{servicio.titulo}':\n{respuesta}"
                ),
                related_object_id=servicio.id,
            )

        messages.success(request, "✅ Respuesta enviada correctamente.")
        return redirect("detalle_servicio", servicio_id=servicio.id)

    return redirect("detalle_servicio", servicio_id=servicio.id)


# ─────────────────────────────────────────────────────────
# CONTRATAR PUBLICACIÓN DE SERVICIO (pasarela de pago)
# ─────────────────────────────────────────────────────────

def contratar_servicio(request):
    """Paso 1: Seleccionar plan y categoría para publicar un servicio."""
    categorias = CategoriaServicio.objects.filter(is_active=True)
    config = _get_config_precios()

    if request.method == "POST":
        tipo_plan = request.POST.get("tipo_plan")  # mensual o anual
        categoria_id = request.POST.get("categoria")
        titulo = request.POST.get("titulo", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        imagen = request.FILES.get("imagen")
        sitio_web = request.POST.get("sitio_web", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        email_contacto = request.POST.get("email_contacto", "").strip()

        if not all([tipo_plan, categoria_id, titulo, descripcion, imagen]):
            messages.error(request, "Todos los campos marcados con * son obligatorios.")
            return render(request, "servicios/contratar_servicio.html", {
                "categorias": categorias,
                "valores": {"mensual": config.valor_mensual, "anual": config.valor_anual},
                "iva": float(config.iva),
                "datos": request.POST,
            })

        monto_base, monto_iva, monto_total = _calcular_pago(tipo_plan)

        # Redirigir al paso de pago con datos en sesión
        request.session["servicio_temp"] = {
            "tipo_plan": tipo_plan,
            "categoria_id": int(categoria_id),
            "titulo": titulo,
            "descripcion": descripcion,
            "sitio_web": sitio_web,
            "telefono": telefono,
            "email_contacto": email_contacto,
            "monto_base": str(monto_base),
            "monto_iva": str(monto_iva),
            "monto_total": str(monto_total),
        }
        # Guardar imagen en sesión no es posible, la pasamos por POST temporal
        if imagen:
            request.session["servicio_temp"]["imagen_name"] = imagen.name
            # Guardamos la imagen en una ubicación temporal manejada por el form de pago
            from django.core.files.storage import default_storage
            import uuid
            temp_path = f"temp_servicio/{uuid.uuid4()}_{imagen.name}"
            default_storage.save(temp_path, imagen)
            request.session["servicio_temp"]["imagen_temp_path"] = temp_path

        return redirect("confirmar_pago_servicio")

    return render(request, "servicios/contratar_servicio.html", {
        "categorias": categorias,
        "valores": {"mensual": config.valor_mensual, "anual": config.valor_anual},
        "iva": float(config.iva),
    })


def _get_config_pago_propiedades():
    """Obtiene la configuración de pago (cuenta corriente) usada en propiedades."""
    try:
        from a03Prop.models import ConfiguracionPagoPubli
        return ConfiguracionPagoPubli.objects.filter(activo=True).first()
    except Exception:
        return None


def _enviar_email_servicio(template_name, subject, recipient, context):
    """Envía email transaccional para el flujo de servicios (Resend/SMTP)."""
    try:
        site_name = getattr(settings, "SITE_NAME", "Serca Propiedades")
        site_domain = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
        html_message = render_to_string(template_name, {
            **context,
            "site_name": site_name,
            "site_domain": site_domain,
        })
        text_message = f"{subject}\n\n{context.get('mensaje_plano', '')}\n\nSerca Propiedades - {site_domain}"
        send_mail(
            subject=f"[{site_name}] {subject}",
            message=text_message,
            from_email=getattr(settings, "EMAIL_NOREPLY_FROM", settings.DEFAULT_FROM_EMAIL),
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception:
        logger.exception("Error enviando email de servicio a %s", recipient)


@login_required
def confirmar_pago_servicio(request):
    """Paso 2: Confirmar pago y subir comprobante.

    El servicio NO se publica automáticamente: queda en estado 'en_revision'.
    Un gerente/superadmin debe validar el contenido y el pago antes de
    iniciar la publicación.
    """
    data = request.session.get("servicio_temp")
    if not data:
        messages.error(request, "No hay datos de servicio pendiente. Comienza desde el inicio.")
        return redirect("contratar_servicio")

    config_pago = _get_config_pago_propiedades()

    if request.method == "POST":
        comprobante = request.FILES.get("comprobante")
        if not comprobante:
            messages.error(request, "Debes subir el comprobante de pago.")
            return render(request, "servicios/confirmar_pago_servicio.html", {
                "data": data,
                "config_pago": config_pago,
            })

        # Obtener imagen temporal y convertir a ContentFile para evitar rutas absolutas
        from django.core.files.base import ContentFile
        imagen = None
        if data.get("imagen_temp_path"):
            from django.core.files.storage import default_storage
            if default_storage.exists(data["imagen_temp_path"]):
                img_bytes = default_storage.open(data["imagen_temp_path"]).read()
                imagen = ContentFile(img_bytes, name=data.get("imagen_name", "servicio.jpg"))

        # Crear el servicio EN REVISIÓN: no se publica hasta aprobación del gerente
        servicio = ServicioPublicitario.objects.create(
            publicante=request.user,
            categoria_id=data["categoria_id"],
            titulo=data["titulo"],
            descripcion=data["descripcion"],
            imagen=imagen,  # puede ser None -> los templates muestran el emoji 🔧
            sitio_web=data.get("sitio_web", ""),
            telefono_contacto=data.get("telefono", ""),
            email_contacto=data.get("email_contacto", ""),
            tipo_plan=data["tipo_plan"],
            monto_pagado=data["monto_total"],
            iva_incluido=True,
            fecha_expiracion=None,  # se asigna al aprobar la publicación
            estado="en_revision",
        )

        # Crear registro de pago
        PagoServicio.objects.create(
            servicio=servicio,
            publicante=request.user,
            tipo_pago=data["tipo_plan"],
            monto_base=data["monto_base"],
            monto_iva=data["monto_iva"],
            monto_total=data["monto_total"],
            comprobante=comprobante,
            estado="pendiente",
        )

        # Limpiar sesión
        if data.get("imagen_temp_path"):
            from django.core.files.storage import default_storage
            try:
                default_storage.delete(data["imagen_temp_path"])
            except Exception:
                pass
        del request.session["servicio_temp"]

        publicante_nombre = request.user.get_full_name() or request.user.email

        # Notificar a gerentes por CDC + email
        gerentes = User.objects.filter(rol__in=["gerente", "superadmin"], is_active=True)
        for g in gerentes:
            _notificar(
                recipient=g,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="🆕 Nuevo servicio en revisión",
                message=(
                    f"{publicante_nombre} contrató el servicio '{servicio.titulo}' "
                    f"(plan {data['tipo_plan']}) por ${int(float(data['monto_total'])):,} CLP. "
                    f"Revisa el contenido y el comprobante antes de publicarlo."
                ),
                related_object_id=servicio.id,
                related_object_type="servicio",
            )
            _enviar_email_servicio(
                "email/servicio_email.html",
                "Nuevo servicio en revisión - Dato Constructor",
                g.email,
                {
                    "tipo_aviso": "nuevo_servicio_admin",
                    "titulo": "🆕 Nuevo servicio contratado pendiente de revisión",
                    "mensaje_plano": (
                        f"{publicante_nombre} ha publicado el servicio '{servicio.titulo}' "
                        f"en Dato Constructor y está pendiente de tu revisión. "
                        f"Ingresa al panel de administración para validar el contenido y el pago."
                    ),
                    "servicio": servicio,
                    "publicante_nombre": publicante_nombre,
                    "monto_total": f"${int(float(data['monto_total'])):,} CLP",
                    "plan_display": servicio.get_tipo_plan_display(),
                },
            )

        messages.success(
            request,
            f"✅ ¡Servicio '{servicio.titulo}' enviado correctamente! "
            f"Quedó en estado 'En revisión': un gerente validará el contenido y el pago "
            f"antes de iniciar la publicación. Te avisaremos por correo y notificación."
        )
        return redirect("gestion_mis_servicios")

    return render(request, "servicios/confirmar_pago_servicio.html", {
        "data": data,
        "config_pago": config_pago,
    })


# ─────────────────────────────────────────────────────────
# GESTIÓN DEL PUBLICANTE
# ─────────────────────────────────────────────────────────

@login_required
def gestion_mis_servicios(request):
    """Panel del publicante: lista sus servicios contratados."""
    servicios = ServicioPublicitario.objects.filter(
        publicante=request.user
    ).select_related("categoria").order_by("-created_at")

    # Contar mensajes no leídos
    for s in servicios:
        s.mensajes_no_leidos = s.mensajes.filter(is_leido=False).count()
        s.total_mensajes = s.mensajes.count()

    return render(request, "servicios/gestion_mis_servicios.html", {
        "servicios": servicios,
    })


@login_required
def subir_imagen_servicio(request, servicio_id):
    """El publicante (o gerente/superadmin) sube o reemplaza la imagen de un servicio."""
    servicio = get_object_or_404(ServicioPublicitario, id=servicio_id)

    # Solo el publicante del servicio, gerente o superadmin pueden editar la imagen
    es_admin = request.user.rol in ("gerente", "superadmin")
    if not es_admin and servicio.publicante_id != request.user.id:
        messages.error(request, "No tienes permisos para modificar esta imagen.")
        return redirect("detalle_servicio", servicio_id=servicio.id)

    # Destino de redirección: si viene desde el detalle, vuelve al detalle
    destino = request.POST.get("next") or "gestion_mis_servicios"

    if request.method != "POST":
        return redirect(destino)

    imagen = request.FILES.get("imagen")
    if not imagen:
        messages.error(request, "Debes seleccionar una imagen.")
        return redirect(destino)

    try:
        imagen.file.seek(0)
    except Exception:
        pass

    try:
        servicio.imagen = imagen
        servicio.save(update_fields=["imagen", "updated_at"])
    except Exception:
        logger.exception("Error al subir imagen del servicio %s", servicio.id)
        messages.error(
            request,
            "No se pudo actualizar la imagen. Verifica que el archivo sea una imagen válida e inténtalo nuevamente.",
        )
        return redirect(destino)

    messages.success(request, "✅ Imagen del servicio actualizada correctamente.")
    return redirect(destino)


@login_required
def log_mensajes_servicio(request, servicio_id):
    """Log de mensajes recibidos para un servicio específico."""
    servicio = get_object_or_404(
        ServicioPublicitario,
        id=servicio_id,
        publicante=request.user,
    )

    mensajes = servicio.mensajes.all().order_by("-created_at")

    if request.method == "POST":
        mensaje_id = request.POST.get("mensaje_id")
        accion = request.POST.get("accion")
        mensaje = get_object_or_404(MensajeServicio, id=mensaje_id, servicio=servicio)

        if accion == "marcar_leido":
            mensaje.is_leido = True
            mensaje.leido_at = timezone.now()
            mensaje.save()
            messages.success(request, "Mensaje marcado como leído.")

        elif accion == "responder":
            respuesta = request.POST.get("respuesta", "").strip()
            if respuesta:
                mensaje.respuesta = respuesta
                mensaje.respondido_at = timezone.now()
                mensaje.is_leido = True
                mensaje.leido_at = mensaje.leido_at or timezone.now()
                mensaje.save()
                messages.success(request, "Respuesta enviada correctamente.")
            else:
                messages.error(request, "Debes escribir una respuesta.")

        return redirect("log_mensajes_servicio", servicio_id=servicio.id)

    return render(request, "servicios/log_mensajes_servicio.html", {
        "servicio": servicio,
        "mensajes": mensajes,
    })


# ─────────────────────────────────────────────────────────
# RATING DE SERVICIOS
# ─────────────────────────────────────────────────────────

@login_required
def calificar_servicio(request, servicio_id):
    """Usuario califica un servicio (1-5 estrellas)."""
    servicio = get_object_or_404(ServicioPublicitario, id=servicio_id, estado="activo")

    if request.method == "POST":
        puntaje = int(request.POST.get("puntaje", 0))
        comentario = request.POST.get("comentario", "").strip()
        nombre_mostrar = request.POST.get("nombre_mostrar", "").strip()

        if puntaje < 1 or puntaje > 5:
            messages.error(request, "El puntaje debe ser entre 1 y 5.")
            return redirect("detalle_servicio", servicio_id=servicio.id)

        # Verificar si ya calificó
        rating_existente = RatingServicio.objects.filter(
            servicio=servicio,
            usuario=request.user,
        ).first()
        if rating_existente:
            rating_existente.puntaje = puntaje
            rating_existente.comentario = comentario
            rating_existente.nombre_mostrar = nombre_mostrar
            rating_existente.save()
            messages.success(request, "✅ Tu calificación ha sido actualizada.")
        else:
            RatingServicio.objects.create(
                servicio=servicio,
                usuario=request.user,
                nombre_mostrar=nombre_mostrar or request.user.get_full_name() or request.user.username,
                puntaje=puntaje,
                comentario=comentario,
            )
            messages.success(request, "✅ Gracias por calificar este servicio.")

        return redirect("detalle_servicio", servicio_id=servicio.id)

    return redirect("detalle_servicio", servicio_id=servicio.id)


# ─────────────────────────────────────────────────────────
# ADMINISTRACIÓN DE SERVICIOS (Gerente/Superadmin)
# ─────────────────────────────────────────────────────────

@login_required
def gestion_admin_servicios(request):
    """Panel de administración de servicios para gerente/superadmin."""
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos para acceder a esta sección.")
        return redirect("home")

    servicios = ServicioPublicitario.objects.all().select_related(
        "categoria", "publicante"
    ).order_by("-created_at")

    pagos_pendientes = PagoServicio.objects.filter(
        estado="pendiente"
    ).select_related("servicio", "publicante")

    servicios_en_revision = ServicioPublicitario.objects.filter(
        estado="en_revision"
    ).select_related("categoria", "publicante").order_by("-created_at")

    servicios_objetados = ServicioPublicitario.objects.filter(
        estado="objetado"
    ).select_related("categoria", "publicante").order_by("-created_at")

    config_precios = _get_config_precios()

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "publicar_servicio":
            servicio_id = request.POST.get("servicio_id")
            servicio = get_object_or_404(ServicioPublicitario, id=servicio_id)
            ok, msg = _aprobar_publicacion_servicio(request, servicio)
            (messages.success if ok else messages.error)(request, msg)

        elif accion == "objetar_servicio":
            servicio_id = request.POST.get("servicio_id")
            servicio = get_object_or_404(ServicioPublicitario, id=servicio_id)
            razon = request.POST.get("razon", "").strip()
            ok, msg = _objetar_publicacion_servicio(request, servicio, razon)
            (messages.warning if ok else messages.error)(request, msg)

        elif accion == "revisar_pago":
            """Reenviar un servicio objetado a revisión (el publicante corrigió)."""
            servicio_id = request.POST.get("servicio_id")
            servicio = get_object_or_404(ServicioPublicitario, id=servicio_id)
            ok, msg = _reenviar_revision_servicio(servicio)
            (messages.success if ok else messages.error)(request, msg)

        elif accion == "aprobar_pago":
            pago_id = request.POST.get("pago_id")
            pago = get_object_or_404(PagoServicio, id=pago_id)
            pago.estado = "aprobado"
            pago.revisado_por = request.user
            pago.save()
            _notificar(
                recipient=pago.publicante,
                emitter=request.user,
                source_type=SourceTypeChoices.GERENTE,
                title="✅ Pago de servicio aprobado",
                message=f"Tu pago por el servicio '{pago.servicio.titulo}' ha sido aprobado.",
                related_object_id=pago.servicio.id,
            )
            _enviar_email_servicio(
                "email/servicio_email.html",
                "Pago aprobado - Dato Constructor",
                pago.publicante.email,
                {
                    "tipo_aviso": "pago_aprobado",
                    "titulo": "✅ Pago de servicio aprobado",
                    "mensaje_plano": (
                        f"Tu pago por el servicio '{pago.servicio.titulo}' "
                        f"(${int(float(pago.monto_total)):,} CLP) ha sido aprobado."
                    ),
                    "servicio": pago.servicio,
                    "publicante_nombre": pago.publicante.get_full_name() or pago.publicante.email,
                    "monto_total": f"${int(float(pago.monto_total)):,} CLP",
                },
            )
            messages.success(request, "Pago aprobado correctamente.")

        elif accion == "rechazar_pago":
            pago_id = request.POST.get("pago_id")
            pago = get_object_or_404(PagoServicio, id=pago_id)
            pago.estado = "rechazado"
            pago.revisado_por = request.user
            pago.save()
            _notificar(
                recipient=pago.publicante,
                emitter=request.user,
                source_type=SourceTypeChoices.GERENTE,
                title="❌ Pago de servicio rechazado",
                message=f"Tu pago por el servicio '{pago.servicio.titulo}' ha sido rechazado. Contacta a administración.",
                related_object_id=pago.servicio.id,
            )
            _enviar_email_servicio(
                "email/servicio_email.html",
                "Pago rechazado - Dato Constructor",
                pago.publicante.email,
                {
                    "tipo_aviso": "pago_rechazado",
                    "titulo": "❌ Pago de servicio rechazado",
                    "mensaje_plano": (
                        f"Tu pago por el servicio '{pago.servicio.titulo}' ha sido rechazado. "
                        f"Contacta a administración para resolver la discrepancia."
                    ),
                    "servicio": pago.servicio,
                    "publicante_nombre": pago.publicante.get_full_name() or pago.publicante.email,
                },
            )
            messages.warning(request, "Pago rechazado.")

        elif accion == "toggle_estado":
            servicio_id = request.POST.get("servicio_id")
            nuevo_estado = request.POST.get("nuevo_estado")
            servicio = get_object_or_404(ServicioPublicitario, id=servicio_id)
            servicio.estado = nuevo_estado
            servicio.save()
            messages.success(request, f"Servicio '{servicio.titulo}' actualizado a '{servicio.get_estado_display()}'.")

        elif accion == "actualizar_precios":
            config = ConfiguracionPrecioServicio.objects.filter(activo=True).first()
            if not config:
                config = ConfiguracionPrecioServicio.objects.create(activo=True)
            try:
                config.valor_mensual = int(request.POST.get("valor_mensual", config.valor_mensual))
                config.valor_anual = int(request.POST.get("valor_anual", config.valor_anual))
                config.iva = float(request.POST.get("iva", config.iva))
                config.save()
                messages.success(request, "✅ Precios de servicios actualizados correctamente.")
            except (ValueError, TypeError):
                messages.error(request, "❌ Valores inválidos. Usa solo números.")

        return redirect("gestion_admin_servicios")

    return render(request, "servicios/gestion_admin_servicios.html", {
        "servicios": servicios,
        "pagos_pendientes": pagos_pendientes,
        "servicios_en_revision": servicios_en_revision,
        "servicios_objetados": servicios_objetados,
        "config_precios": config_precios,
    })


@login_required
def detalle_revision_servicio(request, servicio_id):
    """Detalle de revisión de un servicio para gerente/superadmin.

    Se accede desde el ícono 📋 del Centro de Comunicaciones cuando la
    notificación es de tipo 'servicio'. Permite validar el contenido,
    ver el comprobante de pago y aprobar/objetar la publicación.
    """
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos para acceder a esta sección.")
        return redirect("home")

    servicio = get_object_or_404(
        ServicioPublicitario.objects.select_related("categoria", "publicante", "revisado_por"),
        id=servicio_id,
    )
    pago = servicio.pagos.order_by("-created_at").first()

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "publicar_servicio":
            ok, msg = _aprobar_publicacion_servicio(request, servicio)
            (messages.success if ok else messages.error)(request, msg)

        elif accion == "objetar_servicio":
            razon = request.POST.get("razon", "").strip()
            ok, msg = _objetar_publicacion_servicio(request, servicio, razon)
            (messages.warning if ok else messages.error)(request, msg)

        elif accion == "revisar_pago":
            ok, msg = _reenviar_revision_servicio(servicio)
            (messages.success if ok else messages.error)(request, msg)

        servicio.refresh_from_db()
        pago = servicio.pagos.order_by("-created_at").first()
        return redirect("detalle_revision_servicio", servicio_id=servicio.id)

    return render(request, "servicios/detalle_revision_servicio.html", {
        "servicio": servicio,
        "pago": pago,
    })

# ─────────────────────────────────────────────────────────
# CASOS DE ÉXITO — Público
# ─────────────────────────────────────────────────────────

def lista_casos_exito(request):
    """Lista pública de todos los casos de éxito publicados (servicios + propiedades).
    Si el usuario es gerente/superadmin, también muestra panel CRUD y todos los casos."""
    es_admin = request.user.is_authenticated and request.user.rol in ("gerente", "superadmin")

    casos = CasoExito.objects.filter(is_publicado=True).select_related(
        'servicio', 'servicio__publicante', 'servicio__categoria',
        'propiedad'
    ).order_by('-created_at')

    context = {
        "casos": casos,
    }

    if es_admin:
        # Admin ve también casos no publicados y tiene acceso a CRUD
        todos_casos = CasoExito.objects.all().select_related(
            'servicio', 'servicio__publicante', 'servicio__categoria',
            'propiedad'
        ).order_by('-created_at')
        servicios = ServicioPublicitario.objects.all().select_related('categoria', 'publicante').order_by('-created_at')
        propiedades_opts = []  # No necesitamos listar propiedades aquí, se asocian desde el admin de Django
        context["todos_casos"] = todos_casos
        context["servicios"] = servicios

    return render(request, "servicios/lista_casos_exito.html", context)


def detalle_caso_exito(request, caso_id):
    """Detalle público de un caso de éxito con enlaces al servicio o propiedad relacionados."""
    caso = get_object_or_404(
        CasoExito.objects.select_related(
            'servicio', 'servicio__publicante', 'servicio__categoria',
            'propiedad', 'propiedad__comuna'
        ),
        id=caso_id,
        is_publicado=True,
    )
    return render(request, "servicios/detalle_caso_exito.html", {
        "caso": caso,
    })


# ─────────────────────────────────────────────────────────
# CASOS DE ÉXITO (Admin)
# ─────────────────────────────────────────────────────────

@login_required
def gestion_casos_exito(request):
    """CRUD de casos de éxito para gerente/superadmin. Se accede desde lista_casos_exito."""
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos.")
        return redirect("home")

    if request.method != "POST":
        return redirect("lista_casos_exito")

    accion = request.POST.get("accion")

    if accion == "crear":
        serv_id = request.POST.get("servicio_id") or None
        prop_id = request.POST.get("propiedad_id") or None
        titulo = request.POST.get("titulo", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        cliente_nombre = request.POST.get("cliente_nombre", "").strip()
        cliente_testimonio = request.POST.get("cliente_testimonio", "").strip()
        img_antes = request.FILES.get("imagen_antes")
        img_despues = request.FILES.get("imagen_despues")

        if not all([titulo, descripcion, cliente_nombre]):
            messages.error(request, "Todos los campos marcados (*) son obligatorios.")
            return redirect("lista_casos_exito")

        CasoExito.objects.create(
            servicio_id=serv_id if serv_id else None,
            propiedad_id=prop_id if prop_id else None,
            titulo=titulo,
            descripcion=descripcion,
            imagen_antes=img_antes,
            imagen_despues=img_despues,
            cliente_nombre=cliente_nombre,
            cliente_testimonio=cliente_testimonio,
        )
        messages.success(request, "✅ Caso de éxito creado.")

    elif accion == "toggle":
        caso_id = request.POST.get("caso_id")
        caso = get_object_or_404(CasoExito, id=caso_id)
        caso.is_publicado = not caso.is_publicado
        caso.save()
        estado = "publicado" if caso.is_publicado else "oculto"
        messages.success(request, f"Caso de éxito {estado}.")

    elif accion == "editar":
        caso_id = request.POST.get("caso_id")
        caso = get_object_or_404(CasoExito, id=caso_id)
        caso.titulo = request.POST.get("titulo", caso.titulo).strip()
        caso.descripcion = request.POST.get("descripcion", caso.descripcion).strip()
        caso.cliente_nombre = request.POST.get("cliente_nombre", caso.cliente_nombre).strip()
        caso.cliente_testimonio = request.POST.get("cliente_testimonio", caso.cliente_testimonio).strip()
        serv_id = request.POST.get("servicio_id") or None
        prop_id = request.POST.get("propiedad_id") or None
        caso.servicio_id = int(serv_id) if serv_id else None
        caso.propiedad_id = int(prop_id) if prop_id else None
        if request.FILES.get("imagen_antes"):
            caso.imagen_antes = request.FILES["imagen_antes"]
        if request.FILES.get("imagen_despues"):
            caso.imagen_despues = request.FILES["imagen_despues"]
        caso.save()
        messages.success(request, "✅ Caso de éxito actualizado.")

    elif accion == "eliminar":
        caso_id = request.POST.get("caso_id")
        get_object_or_404(CasoExito, id=caso_id).delete()
        messages.success(request, "🗑️ Caso de éxito eliminado.")

    return redirect("lista_casos_exito")


# ─────────────────────────────────────────────────────────
# API: Datos de propiedad para modal de caso de éxito
# ─────────────────────────────────────────────────────────

@login_required
def api_propiedad_para_caso(request, prop_id):
    """Retorna datos de una propiedad vendida/arrendada para pre-poblar el modal de caso de éxito."""
    if request.user.rol not in ("gerente", "superadmin"):
        return JsonResponse({"error": "No autorizado"}, status=403)

    try:
        from a03Prop.models import Propiedad
        prop = Propiedad.objects.get(id=prop_id)
    except Propiedad.DoesNotExist:
        return JsonResponse({"error": "Propiedad no encontrada"}, status=404)

    if not prop.tipo_cierre:
        return JsonResponse({"error": "La propiedad no está marcada como vendida/arrendada"}, status=400)

    primera_foto = prop.fotos.first()
    foto_url = primera_foto.imagen.url if primera_foto and primera_foto.imagen else ""

    data = {
        "id": prop.id,
        "titulo": f"{prop.get_tipo_prop_display()} - {prop.calle} #{prop.numero_calle}",
        "tipo_prop": prop.get_tipo_prop_display(),
        "tipo_accion": prop.get_tipo_accion_display(),
        "comuna": str(prop.comuna) if prop.comuna else "",
        "tipo_cierre": prop.get_tipo_cierre_display() if prop.tipo_cierre else "",
        "precio": float(prop.precio),
        "moneda": prop.get_tipo_moneda_display(),
        "dormitorios": prop.numero_dormitorios,
        "banos": prop.numero_banos,
        "m_construidos": float(prop.m_construidos) if prop.m_construidos else None,
        "foto_url": foto_url,
        "cliente_nombre": prop.dueno.get_full_name() or prop.dueno.email if prop.dueno else "",
        "descripcion": prop.descripcion_propiedad or "",
    }
    return JsonResponse(data)


# ─────────────────────────────────────────────────────────
# API: Obtener servicios para el bloque del home
# ─────────────────────────────────────────────────────────

def servicios_para_home(request):
    """Retorna servicios activos para mostrar en la home (usado como partial o API)."""
    servicios = ServicioPublicitario.objects.filter(
        estado="activo",
        fecha_expiracion__gte=timezone.now(),
    ).select_related("categoria", "publicante").order_by("-created_at")[:6]
    return servicios
