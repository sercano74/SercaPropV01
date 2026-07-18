import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
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


def _notificar(recipient, emitter, source_type, title, message, related_object_id=None):
    return Communication.objects.create(
        recipient=recipient,
        emitter_user=emitter,
        source_type=source_type,
        title=title,
        message=message,
        related_object_id=related_object_id,
    )


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

    return render(request, "servicios/detalle_servicio.html", {
        "servicio": servicio,
        "casos_exito": casos_exito,
        "ratings": ratings,
        "datos_contacto": datos_contacto,
    })


# ─────────────────────────────────────────────────────────
# ENVÍO DE MENSAJE AL PUBLICANTE
# ─────────────────────────────────────────────────────────

def enviar_mensaje_servicio(request, servicio_id):
    """Usuario envía un mensaje al publicante del servicio."""
    servicio = get_object_or_404(ServicioPublicitario, id=servicio_id, estado="activo")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        email = request.POST.get("email", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        mensaje_texto = request.POST.get("mensaje", "").strip()

        if not all([nombre, email, telefono, mensaje_texto]):
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect("detalle_servicio", servicio_id=servicio.id)

        MensajeServicio.objects.create(
            servicio=servicio,
            nombre_remitente=nombre,
            email_remitente=email,
            telefono_remitente=telefono,
            mensaje=mensaje_texto,
        )

        # Notificar al publicante
        _notificar(
            recipient=servicio.publicante,
            emitter=request.user if request.user.is_authenticated else servicio.publicante,
            source_type=SourceTypeChoices.USUARIO_BASE if request.user.is_authenticated else SourceTypeChoices.SISTEMA,
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


@login_required
def confirmar_pago_servicio(request):
    """Paso 2: Confirmar pago y subir comprobante."""
    data = request.session.get("servicio_temp")
    if not data:
        messages.error(request, "No hay datos de servicio pendiente. Comienza desde el inicio.")
        return redirect("contratar_servicio")

    if request.method == "POST":
        comprobante = request.FILES.get("comprobante")
        if not comprobante:
            messages.error(request, "Debes subir el comprobante de pago.")
            return render(request, "servicios/confirmar_pago_servicio.html", {
                "data": data,
            })

        # Obtener imagen temporal y convertir a ContentFile para evitar rutas absolutas
        from django.core.files.base import ContentFile
        imagen = None
        if data.get("imagen_temp_path"):
            from django.core.files.storage import default_storage
            if default_storage.exists(data["imagen_temp_path"]):
                img_bytes = default_storage.open(data["imagen_temp_path"]).read()
                imagen = ContentFile(img_bytes, name=data.get("imagen_name", "servicio.jpg"))

        # Determinar duración
        meses = 12 if data["tipo_plan"] == "anual" else 1
        fecha_expiracion = timezone.now() + timedelta(days=30 * meses)

        # Crear el servicio
        servicio = ServicioPublicitario.objects.create(
            publicante=request.user,
            categoria_id=data["categoria_id"],
            titulo=data["titulo"],
            descripcion=data["descripcion"],
            imagen=imagen or "servicios/placeholder.jpg",
            sitio_web=data.get("sitio_web", ""),
            telefono_contacto=data.get("telefono", ""),
            email_contacto=data.get("email_contacto", ""),
            tipo_plan=data["tipo_plan"],
            monto_pagado=data["monto_total"],
            iva_incluido=True,
            fecha_expiracion=fecha_expiracion,
            estado="activo",
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

        # Notificar a gerentes
        gerentes = User.objects.filter(rol__in=["gerente", "superadmin"], is_active=True)
        for g in gerentes:
            _notificar(
                recipient=g,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="Nuevo servicio contratado - Pendiente de revisión",
                message=f"{request.user.get_full_name() or request.user.email} ha contratado el servicio '{servicio.titulo}' (plan {data['tipo_plan']}).",
                related_object_id=servicio.id,
            )

        messages.success(
            request,
            f"✅ ¡Servicio '{servicio.titulo}' creado exitosamente! "
            f"Tu publicación está activa hasta el {servicio.fecha_expiracion.strftime('%d/%m/%Y')}. "
            f"Recibirás los mensajes de los interesados en tu panel de gestión."
        )
        return redirect("gestion_mis_servicios")

    return render(request, "servicios/confirmar_pago_servicio.html", {
        "data": data,
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

    config_precios = _get_config_precios()

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "aprobar_pago":
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
        "config_precios": config_precios,
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
