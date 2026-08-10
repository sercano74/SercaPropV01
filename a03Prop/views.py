from datetime import datetime, date
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q
from .models import (
    Propiedad,
    PublicacionProp,
    CorredorProp,
    FotosPropiedad,
    LegalDocsProp,
    ConfiguracionPagoPubli,
    ServiciosProp,
    SolicitudPublicacion,
    ObservacionSolicitud,
    FavoritaProp,
    SolicitudVisita,
    PropuestaCompra,
    ProcesoCompra,
    ObservacionProceso,
    CierreEconomico,
)
from a01Com.models import Communication, SourceTypeChoices
from a00seg.models import User, Comuna, Region, AgendaCorredor
from decimal import Decimal

logger = logging.getLogger(__name__)


def _get_docs_orientacion_texto(tipo_accion):
    """
    Retorna el texto de orientación sobre documentos legales requeridos
    según el tipo de acción (venta, arriendo, srt).
    """
    texto_venta = (
        "Documentos requeridos para VENTA:\n"
        "- Escritura de Compraventa vigente\n"
        "- Dominio vigente con copia de la inscripción (siempre) - Conservador de Bienes Raíces (¿Es el dueño?)\n"
        "- Certificado de Hipotecas y Gravámenes (siempre) - Conservador de Bienes Raíces (¿se puede vender?)\n"
        "- Certificado de Recepción Final - Dirección de Obras Municipales (DOM)\n"
        "- Certificado de No Expropiación - Dirección de Obras Municipales (DOM)\n"
        "- Certificado de No Expropiación (siempre) - Servicio de Vivienda y Urbanismo (SERVIU)\n"
        "- Certificados de deudas (siempre) - Tesorería General de la República / gasto común / Dº de aseo / servicios básicos y contribuciones\n"
        "- Certificado de avalúo fiscal (siempre) - Servicio de Impuestos Internos (SII)\n"
        "- Certificado de Informes Previos (CIP) - Dirección de Obras Municipales (terrenos y bienes comerciales)\n"
        "- Certificado de estado civil (siempre) - Registro Civil\n"
        "- Foto de Cédula de identidad del Propietario(s) por ambos lados"
    )
    texto_arriendo_str = (
        "Documentos requeridos para ARRIENDO / SRT:\n"
        "- Dominio vigente con copia de la inscripción (siempre) - Conservador de Bienes Raíces (¿Es el dueño?)\n"
        "- Foto de Cédula de identidad del Propietario(s) por ambos lados\n"
        "- Poder Notarial de un tercero para representar (si aplica)"
    )

    if tipo_accion == "venta":
        return texto_venta
    elif tipo_accion in ("arriendo", "srt"):
        return texto_arriendo_str
    # Fallback: texto más completo (venta)
    return texto_venta


def detalle_propiedad_redirect(request, prop_id):
    """Redirige 301 desde la URL antigua (solo ID) a la canónica con slug SEO."""
    try:
        propiedad = Propiedad.objects.get(id=prop_id)
    except Propiedad.DoesNotExist:
        messages.warning(request, "La propiedad que buscas no existe o ha sido removida.")
        return redirect("home")

    slug = propiedad.slug or f"propiedad-{propiedad.id}"
    return redirect("detalle_propiedad_slug", prop_id=propiedad.id, prop_slug=slug, permanent=True)


def detalle_propiedad(request, prop_id, prop_slug=None):
    try:
        propiedad = Propiedad.objects.get(id=prop_id)
    except Propiedad.DoesNotExist:
        messages.warning(request, "La propiedad que buscas no existe o ha sido removida.")
        return redirect("home")

    # ===== SEO: Canonical URL =====
    # Si el slug no coincide con el canónico, redirigir 301 a la URL correcta
    slug_canonico = propiedad.slug or f"propiedad-{propiedad.id}"
    if prop_slug != slug_canonico:
        return redirect(
            "detalle_propiedad_slug",
            prop_id=propiedad.id,
            prop_slug=slug_canonico,
            permanent=True,
        )

    fotos = propiedad.fotos.all()
    publicacion = propiedad.publicaciones.filter(estado="publicada").first()

    solicitud = SolicitudPublicacion.objects.filter(
        propiedad=propiedad
    ).exclude(
        estado__in=["rechazada", "cancelada"]
    ).first()

    servicios = ServiciosProp.objects.filter(is_active=True)
    corredores_disponibles = User.objects.filter(rol="corredor", is_active=True)

    # Solo el dueño, corredor, gerente o superadmin puede ver
    # publicación, corredor asignado, proceso de publicación y siguientes procesos
    if request.user.is_authenticated:
        puede_ver_restricted = (
            request.user == propiedad.dueno
            or request.user.rol in ("corredor", "gerente", "superadmin")
        )
    else:
        puede_ver_restricted = False

    # --- Solicitudes de visita ---
    visitas_qs = SolicitudVisita.objects.filter(propiedad=propiedad).select_related(
        "usuario", "corredor", "bloque_agenda"
    )

    # Filtro por visibilidad:
    if request.user.is_authenticated:
        if request.user.rol in ("gerente", "superadmin"):
            pass  # ve todas
        elif request.user == propiedad.dueno:
            pass  # dueño ve todas las de su propiedad
        elif request.user.rol == "corredor":
            visitas_qs = visitas_qs.filter(corredor=request.user)
        else:
            visitas_qs = visitas_qs.filter(usuario=request.user)
    else:
        visitas_qs = SolicitudVisita.objects.none()

    # Ordenar: primero por usuario, luego por created_at descendente dentro del usuario
    visitas_list = list(visitas_qs.order_by("usuario_id", "-created_at"))

    # Agrupar visitas por usuario para los accordions anidados
    visitas_por_usuario = {}
    for v in visitas_list:
        uid = v.usuario_id
        if uid not in visitas_por_usuario:
            # Guardar la última visita realizada o la más avanzada para determinar estado del usuario
            ultima = v
            visitas_por_usuario[uid] = {
                "usuario": v.usuario,
                "visitas": [],
                "ultima_visita": ultima,
            }
        visitas_por_usuario[uid]["visitas"].append(v)
        # Actualizar últimas
        if v.created_at > visitas_por_usuario[uid]["ultima_visita"].created_at:
            visitas_por_usuario[uid]["ultima_visita"] = v

    # Propuestas (visibles según rol) - traer también procesos asociados
    propuestas = PropuestaCompra.objects.filter(
        solicitud_visita__propiedad=propiedad
    ).select_related("solicitud_visita__usuario").prefetch_related("proceso")

    if request.user.is_authenticated:
        if request.user.rol in ("gerente", "superadmin"):
            pass  # ve todas
        elif request.user == propiedad.dueno:
            pass  # ve todas las de su propiedad
        elif request.user.rol == "corredor":
            propuestas = propuestas.filter(solicitud_visita__corredor=request.user)
        else:
            propuestas = propuestas.filter(solicitud_visita__usuario=request.user)
    else:
        propuestas = PropuestaCompra.objects.none()

    # Indexar propuestas por visita_id para acceso rápido
    propuestas_por_visita = {p.solicitud_visita_id: p for p in propuestas}

    # Procesos de compra visibles: los activos (cualquier estado no terminal)
    # + los finalizados/cancelados de los últimos 15 días desde su completado
    quince_dias_atras = timezone.now() - timezone.timedelta(days=15)
    procesos_compra = ProcesoCompra.objects.filter(
        propiedad=propiedad
    ).filter(
        # Activos: cualquier estado excepto finalizado/cancelado
        ~Q(estado__in=["finalizado", "cancelado"])
        # O finalizados/cancelados pero dentro de los últimos 15 días
        | Q(
            estado__in=["finalizado", "cancelado"],
            completado_at__gte=quince_dias_atras,
        )
        # O finalizados/cancelados sin completado_at pero con fecha_cierre de la propiedad dentro de 15 días
        | Q(
            estado__in=["finalizado", "cancelado"],
            completado_at__isnull=True,
            propiedad__fecha_cierre__gte=quince_dias_atras,
        )
    ).select_related(
        "propuesta__solicitud_visita__usuario", "comprador", "corredor"
    ).order_by("-created_at")

    # Visita activa del usuario actual (si existe)
    visita_activa = None
    visitas_rechazadas = False
    if request.user.is_authenticated and not (request.user.rol in ("gerente", "superadmin") or request.user == propiedad.dueno):
        visita_activa = SolicitudVisita.objects.filter(
            usuario=request.user,
            propiedad=propiedad,
            estado__in=["pendiente", "aceptada", "reprogramada", "realizada"],
        ).first()
        # Ver si hay visitas rechazadas para mostrar mensaje de reintento
        visitas_rechazadas = SolicitudVisita.objects.filter(
            usuario=request.user,
            propiedad=propiedad,
            estado="rechazada",
        ).exists()

    # Verificar si hay un proceso activo que pause otros
    proceso_activo = ProcesoCompra.objects.filter(
        propiedad=propiedad,
        estado__in=[
            "propuesta_aceptada", "promesa_observacion", "promesa_aceptada",
            "instrucciones_observacion", "instrucciones_aceptada",
            "contrato_pendiente", "contrato_listo", "firma_notarial",
            "escritura_cbr", "escritura_rechazada",
        ],
    ).first()

    # ===== Verificar si el corredor asignado tiene agenda =====
    corredor_tiene_agenda = False
    cp = _get_corredor_activo(propiedad)
    if cp:
        hoy = timezone.localdate()
        ahora = timezone.localtime().time()
        bloques_disponibles = AgendaCorredor.objects.filter(
            corredor=cp.corredor,
            activo=True,
            reservado=False,
            fecha__gte=hoy,
        )
        # Filtrar bloques de hoy que ya pasaron
        bloques_futuros = [b for b in bloques_disponibles if b.fecha > hoy or b.hora_inicio > ahora]
        corredor_tiene_agenda = len(bloques_futuros) > 0

    # ===== Datos para edición y docs legales =====
    corredor_prop = None
    puede_editar_propiedad = False
    if request.user.is_authenticated:
        puede_editar_propiedad = _puede_editar_propiedad(request, propiedad)
        if cp:
            corredor_prop = cp

    docs_legales = propiedad.docs_legales.all().order_by("-uploaded_at")

    solicitud_docs_requeridos = []
    if solicitud and solicitud.docs_requeridos:
        solicitud_docs_requeridos = [d.strip() for d in solicitud.docs_requeridos.split(",") if d.strip()]

    # Casos de éxito asociados a esta propiedad
    from a07serv.models import CasoExito as CasoExitoModel
    casos_exito_propiedad = CasoExitoModel.objects.filter(
        propiedad=propiedad, is_publicado=True
    ).order_by('-created_at')

    return render(request, "detalle_propiedad.html", {
        "propiedad": propiedad,
        "fotos": fotos,
        "publicacion": publicacion,
        "solicitud": solicitud,
        "servicios": servicios,
        "corredores_disponibles": corredores_disponibles,
        "puede_ver_restricted": puede_ver_restricted,
        "visitas_por_usuario": visitas_por_usuario,
        "visitas_list": visitas_list,
        "propuestas": propuestas,
        "propuestas_por_visita": propuestas_por_visita,
        "visita_activa": visita_activa,
        "visitas_rechazadas": visitas_rechazadas,
        "procesos_compra": procesos_compra,
        "proceso_activo": proceso_activo,
        # Nuevos contextos para edición y docs
        "puede_editar_propiedad": puede_editar_propiedad,
        "corredor_prop": corredor_prop,
        "corredor_tiene_agenda": corredor_tiene_agenda,
        "docs_legales": docs_legales,
        "solicitud_docs_requeridos": solicitud_docs_requeridos,
        "casos_exito_propiedad": casos_exito_propiedad,
    })


@login_required
def asignar_corredor(request, prop_id):
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos para asignar corredores.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    propiedad = get_object_or_404(Propiedad, id=prop_id)
    corredores = User.objects.filter(rol="corredor", is_active=True)

    if request.method == "POST":
        corredor_id = request.POST.get("corredor_id")
        corredor = get_object_or_404(User, id=corredor_id, rol="corredor")

        CorredorProp.objects.create(
            propiedad=propiedad,
            corredor=corredor,
            tipo_comision=request.POST.get("tipo_comision", "porcentaje"),
            monto_comision_usu=request.POST.get("monto_comision_usu") or None,
            monto_comision_dueno=request.POST.get("monto_comision_dueno") or None,
            estado="activa",
        )

        Communication.objects.create(
            recipient=corredor,
            emitter_user=request.user,
            source_type=SourceTypeChoices.GERENTE,
            title="Nueva asignación de propiedad",
            message=f"Se te ha asignado la propiedad: {propiedad.display_name_public()}",
            property_id=propiedad.id,
        )

        messages.success(request, f"Corredor {corredor.get_full_name()} asignado a la propiedad.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    return render(request, "asignar_corredor.html", {
        "propiedad": propiedad,
        "corredores": corredores,
    })


@login_required
def aprobar_publicacion(request, pub_id):
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos para aprobar publicaciones.")
        return redirect("home")

    publicacion = get_object_or_404(PublicacionProp, id=pub_id)
    meses = publicacion.meses

    publicacion.estado = "publicada"
    publicacion.inicia_at = timezone.now()
    publicacion.expira_at = timezone.now() + timezone.timedelta(days=30 * meses)
    publicacion.save()

    publicacion.propiedad.estado = "publicada"
    publicacion.propiedad.save()

    Communication.objects.create(
        recipient=publicacion.publicante,
        emitter_user=request.user,
        source_type=SourceTypeChoices.GERENTE,
        title="Publicación aprobada",
        message=f"Tu publicación para {publicacion.propiedad.display_name_public()} ha sido aprobada y está visible.",
        property_id=publicacion.propiedad.id,
    )

    messages.success(request, "Publicación aprobada exitosamente.")
    return redirect("gestion")


@login_required
def rechazar_publicacion(request, pub_id):
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos.")
        return redirect("home")

    publicacion = get_object_or_404(PublicacionProp, id=pub_id)
    publicacion.estado = "objetada"
    publicacion.save()

    Communication.objects.create(
        recipient=publicacion.publicante,
        emitter_user=request.user,
        source_type=SourceTypeChoices.GERENTE,
        title="Publicación objetada",
        message=f"Tu publicación para {publicacion.propiedad.display_name_public()} ha sido objetada. Razón: {request.POST.get('razon', 'Sin especificar')}",
        property_id=publicacion.propiedad.id,
    )

    messages.warning(request, "Publicación rechazada / objetada.")
    return redirect("gestion")


@login_required
def renovar_publicacion(request, pub_id):
    publicacion = get_object_or_404(PublicacionProp, id=pub_id, publicante=request.user)
    config_pago = ConfiguracionPagoPubli.objects.filter(activo=True).first()

    if request.method == "POST":
        meses_extra = int(request.POST.get("meses", 1))
        es_destacada = request.POST.get("es_destacada") == "1"

        if config_pago:
            if es_destacada:
                if publicacion.propiedad.tipo_accion == "venta":
                    valor_base = config_pago.valor_destacado_venta_mensual
                elif publicacion.propiedad.tipo_accion == "arriendo":
                    valor_base = config_pago.valor_destacado_arriendo_mensual
                else:
                    valor_base = config_pago.valor_destacado_str_dia
            else:
                if publicacion.propiedad.tipo_accion == "venta":
                    valor_base = config_pago.valor_pub_venta_mensual
                elif publicacion.propiedad.tipo_accion == "arriendo":
                    valor_base = config_pago.valor_pub_arriendo_mensual
                else:
                    valor_base = config_pago.valor_pub_str_dia
            total = valor_base * meses_extra
        else:
            total = 0

        nueva = PublicacionProp.objects.create(
            propiedad=publicacion.propiedad,
            publicante=request.user,
            meses=meses_extra,
            es_destacada=es_destacada,
            total_pago=total,
            comprobante=request.FILES.get("comprobante"),
            estado="en_revision",
        )

        publicacion.estado = "renovada"
        publicacion.save()

        messages.success(request, "Solicitud de renovación enviada. Queda pendiente de revisión.")
        return redirect("gestion")

    return render(request, "renovar_publicacion.html", {
        "publicacion": publicacion,
        "config_pago": config_pago,
    })


@login_required
def archivar_propiedad(request, prop_id):
    propiedad = get_object_or_404(Propiedad, id=prop_id, dueno=request.user)
    propiedad.estado = "archivada"
    propiedad.save()

    propiedad.publicaciones.filter(estado="publicada").update(estado="archivada")

    messages.success(request, "Propiedad archivada correctamente.")
    return redirect("detalle_propiedad", prop_id=prop_id)


def buscar_propiedades_api(request):
    """API endpoint for property search"""
    tipo_accion = request.GET.get("tipo_accion")
    tipo_prop = request.GET.get("tipo_prop")
    comuna_id = request.GET.get("comuna")
    search = request.GET.get("q")

    treinta_dias_atras = timezone.now() - timezone.timedelta(days=30)

    publicadas = PublicacionProp.objects.filter(
        estado="publicada", expira_at__gte=timezone.now()
    ).select_related("propiedad")

    # Incluir propiedades cerradas dentro de los últimos 30 días (NO destacadas)
    cerradas_recientes = PublicacionProp.objects.filter(
        estado="publicada",
        es_destacada=False,  # excluir destacadas → la propiedad ya no destaca tras cierre
        propiedad__tipo_cierre__isnull=False,
        propiedad__fecha_cierre__gte=treinta_dias_atras,
    ).select_related("propiedad")
    publicadas = (publicadas | cerradas_recientes).distinct()

    if tipo_accion:
        publicadas = publicadas.filter(propiedad__tipo_accion=tipo_accion)
    if tipo_prop:
        publicadas = publicadas.filter(propiedad__tipo_prop=tipo_prop)
    if comuna_id:
        publicadas = publicadas.filter(propiedad__comuna_id=comuna_id)
    if search:
        publicadas = publicadas.filter(
            Q(propiedad__calle__icontains=search) |
            Q(propiedad__descripcion_propiedad__icontains=search)
        )

    data = []
    for p in publicadas[:50]:
        foto_url = ""
        primera_foto = p.propiedad.fotos.first()
        if primera_foto and primera_foto.imagen:
            foto_url = primera_foto.imagen.url

        data.append({
            "id": p.id,
            "propiedad_id": p.propiedad.id,
            "titulo": f"{p.propiedad.get_tipo_prop_display()} - {p.propiedad.calle} #{p.propiedad.numero_calle}",
            "tipo_prop": p.propiedad.get_tipo_prop_display(),
            "tipo_accion": p.propiedad.get_tipo_accion_display(),
            "precio": float(p.propiedad.precio),
            "moneda": p.propiedad.get_tipo_moneda_display(),
            "comuna": str(p.propiedad.comuna) if p.propiedad.comuna else "",
            "dormitorios": p.propiedad.numero_dormitorios,
            "banos": p.propiedad.numero_banos,
            "m_construidos": float(p.propiedad.m_construidos) if p.propiedad.m_construidos else None,
            "m_terreno": float(p.propiedad.m_terreno) if p.propiedad.m_terreno else None,
            "foto_url": foto_url,
            "url": f"/prop/detalle/{p.propiedad.id}/",
        })

    return JsonResponse({"data": data})


# ================================================================
# LANDING PAGES SEO (por comuna / categoría)
# ================================================================

def landing_propiedades(request, accion, tipo_prop, comuna_slug):
    """Landing page de propiedades publicadas en una comuna para una
    acción (venta/arriendo/srt) y tipo (casa/departamento/...).

    Estas páginas capturan búsquedas del tipo "departamento en arriendo
    providencia" y enlazan a los detalles canónicos de cada propiedad.
    """
    comuna = get_object_or_404(Comuna, slug=comuna_slug)

    acciones_validas = dict(Propiedad.TIPO_ACCION_CHOICES)
    tipos_validos = dict(Propiedad.TIPO_PROP_CHOICES)
    if accion not in acciones_validas or tipo_prop not in tipos_validos:
        raise Http404("Combinación de acción/tipo/comuna no válida.")

    publicadas = PublicacionProp.objects.filter(
        estado="publicada",
        expira_at__gte=timezone.now(),
        propiedad__comuna=comuna,
        propiedad__tipo_accion=accion,
        propiedad__tipo_prop=tipo_prop,
    ).select_related("propiedad").prefetch_related("propiedad__fotos").order_by("-es_destacada", "-inicia_at")

    return render(request, "landing_propiedades.html", {
        "comuna": comuna,
        "accion": accion,
        "accion_display": acciones_validas[accion],
        "tipo_prop": tipo_prop,
        "tipo_prop_display": tipos_validos[tipo_prop],
        "publicadas": publicadas,
        "total": publicadas.count(),
    })


# ================================================================
# EDICIÓN DE PROPIEDAD (gerente, superadmin, corredor asignado, dueño)
# ================================================================

def _get_corredor_activo(propiedad):
    """Obtiene el CorredorProp activo de una propiedad."""
    return CorredorProp.objects.filter(
        propiedad=propiedad, estado="activa"
    ).select_related("corredor").first()


def _puede_editar_propiedad(request, propiedad):
    """
    Determina si el usuario puede editar la propiedad según su rol y los switches de permiso.
    - Gerente/Superadmin: siempre pueden editar
    - Corredor asignado: solo si corredor_puede_editar = True
    - Dueño: solo si dueno_puede_editar = True y corredor_puede_editar = True (el dueño solo edita si el corredor también puede)
    """
    user = request.user
    if not user.is_authenticated:
        return False
    if user.rol in ("gerente", "superadmin"):
        return True
    cp = _get_corredor_activo(propiedad)
    if user.rol == "corredor" and cp and cp.corredor == user:
        return cp.corredor_puede_editar
    if user == propiedad.dueno:
        # Dueño solo edita si el corredor activo le ha dado permiso
        if cp and cp.dueno_puede_editar and cp.corredor_puede_editar:
            return True
        # Si no hay corredor asignado, el dueño SIEMPRE puede editar
        if not cp:
            return True
        return False
    return False


@login_required
def editar_propiedad(request, prop_id):
    """Página de edición de propiedad (datos + fotos + docs legales)."""
    propiedad = get_object_or_404(Propiedad, id=prop_id)

    if not _puede_editar_propiedad(request, propiedad):
        messages.error(request, "No tienes permiso para editar esta propiedad.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    solicitud = SolicitudPublicacion.objects.filter(
        propiedad=propiedad
    ).exclude(
        estado__in=["rechazada", "cancelada"]
    ).first()

    docs_requeridos_lista = []
    if solicitud and solicitud.docs_requeridos:
        docs_requeridos_lista = [d.strip() for d in solicitud.docs_requeridos.split(",") if d.strip()]

    servicios = ServiciosProp.objects.filter(is_active=True)
    comunas = Comuna.objects.all().order_by("nombre")

    docs_legales = propiedad.docs_legales.all().order_by("-uploaded_at")

    if request.method == "POST":
        comuna_id = request.POST.get("comuna")
        if comuna_id:
            propiedad.comuna_id = comuna_id
        propiedad.tipo_uso = request.POST.get("tipo_uso", propiedad.tipo_uso)
        propiedad.numero_dormitorios = request.POST.get("numero_dormitorios", 0)
        propiedad.numero_banos = request.POST.get("numero_banos", 0)
        propiedad.m_construidos = request.POST.get("m_construidos") or None
        propiedad.m_terreno = request.POST.get("m_terreno") or None
        propiedad.num_estacionamientos = request.POST.get("num_estacionamientos", 0)
        propiedad.tiene_bodega = request.POST.get("tiene_bodega") == "1"
        propiedad.descripcion_propiedad = request.POST.get("descripcion_propiedad", "")
        propiedad.descripcion_entorno = request.POST.get("descripcion_entorno", "")
        propiedad.tipo_moneda = request.POST.get("tipo_moneda", propiedad.tipo_moneda)
        propiedad.precio = request.POST.get("precio", propiedad.precio)
        propiedad.save()

        servicios_ids = request.POST.getlist("servicios")
        if servicios_ids:
            propiedad.servicios_prop.set(servicios_ids)
        else:
            propiedad.servicios_prop.clear()

        messages.success(request, "✅ Propiedad actualizada correctamente.")
        return redirect("editar_propiedad", prop_id=prop_id)

    corredor_prop = _get_corredor_activo(propiedad)

    return render(request, "editar_propiedad.html", {
        "propiedad": propiedad,
        "solicitud": solicitud,
        "servicios": servicios,
        "comunas": comunas,
        "docs_legales": docs_legales,
        "docs_requeridos_lista": docs_requeridos_lista,
        "corredor_prop": corredor_prop,
    })


@login_required
def toggle_permiso_editar_corredor(request, prop_id):
    """
    Gerente/superadmin activa/desactiva que el corredor pueda editar la propiedad.
    """
    if request.user.rol not in ("gerente", "superadmin"):
        return JsonResponse({"success": False, "error": "No tienes permiso"}, status=403)

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    propiedad = get_object_or_404(Propiedad, id=prop_id)
    cp = _get_corredor_activo(propiedad)
    if not cp:
        return JsonResponse({"success": False, "error": "No hay corredor asignado"}, status=400)

    cp.corredor_puede_editar = not cp.corredor_puede_editar
    cp.save(update_fields=["corredor_puede_editar"])

    return JsonResponse({
        "success": True,
        "corredor_puede_editar": cp.corredor_puede_editar,
        "msg": f"Permiso de edición para corredor {'activado' if cp.corredor_puede_editar else 'desactivado'}",
    })


@login_required
def toggle_permiso_editar_dueno(request, prop_id):
    """
    Corredor (o gerente/superadmin) activa/desactiva que el dueño pueda editar la propiedad.
    """
    propiedad = get_object_or_404(Propiedad, id=prop_id)
    cp = _get_corredor_activo(propiedad)

    es_corredor = request.user.rol == "corredor" and cp and cp.corredor == request.user
    es_admin = request.user.rol in ("gerente", "superadmin")

    if not (es_corredor or es_admin):
        return JsonResponse({"success": False, "error": "No tienes permiso"}, status=403)

    if not cp:
        return JsonResponse({"success": False, "error": "No hay corredor asignado"}, status=400)

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    cp.dueno_puede_editar = not cp.dueno_puede_editar
    cp.save(update_fields=["dueno_puede_editar"])

    return JsonResponse({
        "success": True,
        "dueno_puede_editar": cp.dueno_puede_editar,
        "msg": f"Permiso de edición para dueño {'activado' if cp.dueno_puede_editar else 'desactivado'}",
    })


@login_required
def subir_foto_propiedad(request, prop_id):
    """Sube una foto a la propiedad en la página de edición."""
    propiedad = get_object_or_404(Propiedad, id=prop_id)

    if not _puede_editar_propiedad(request, propiedad):
        messages.error(request, "No tienes permiso.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    if request.method == "POST":
        imagen = request.FILES.get("imagen")
        if not imagen:
            messages.error(request, "Debes seleccionar una imagen.")
            return redirect("editar_propiedad", prop_id=prop_id)

        FotosPropiedad.objects.create(propiedad=propiedad, imagen=imagen)
        messages.success(request, "📸 Foto subida correctamente.")
        return redirect("editar_propiedad", prop_id=prop_id)

    return redirect("editar_propiedad", prop_id=prop_id)


@login_required
def eliminar_foto_propiedad(request, foto_id):
    """Elimina una foto de la propiedad (AJAX)."""
    foto = get_object_or_404(FotosPropiedad, id=foto_id)

    if not _puede_editar_propiedad(request, foto.propiedad):
        return JsonResponse({"success": False, "error": "No tienes permiso"}, status=403)

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    foto.delete()
    return JsonResponse({"success": True})


@login_required
def subir_documento_legal(request, prop_id):
    """Sube un nuevo documento legal a la propiedad."""
    propiedad = get_object_or_404(Propiedad, id=prop_id)

    if not _puede_editar_propiedad(request, propiedad):
        messages.error(request, "No tienes permiso.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        documento = request.FILES.get("documento")
        if not nombre or not documento:
            messages.error(request, "Debes indicar nombre y seleccionar archivo.")
            return redirect("editar_propiedad", prop_id=prop_id)

        LegalDocsProp.objects.create(
            propiedad=propiedad,
            nombre=nombre,
            documento=documento,
            estado="pendiente",
        )
        messages.success(request, f"📄 Documento '{nombre}' subido correctamente.")
        return redirect("editar_propiedad", prop_id=prop_id)

    return redirect("editar_propiedad", prop_id=prop_id)


@login_required
def reemplazar_documento_legal(request, doc_id):
    """Reemplaza el archivo de un documento legal existente."""
    doc = get_object_or_404(LegalDocsProp, id=doc_id)

    if not _puede_editar_propiedad(request, doc.propiedad):
        messages.error(request, "No tienes permiso.")
        return redirect("detalle_propiedad", prop_id=doc.propiedad.id)

    if request.method == "POST":
        nuevo_documento = request.FILES.get("documento")
        if not nuevo_documento:
            messages.error(request, "Debes seleccionar un archivo.")
            return redirect("editar_propiedad", prop_id=doc.propiedad.id)

        doc.documento = nuevo_documento
        doc.estado = "pendiente"  # resetear estado al reemplazar
        doc.save(update_fields=["documento", "estado", "updated_at"])
        messages.success(request, f"🔄 Documento '{doc.nombre}' reemplazado.")
        return redirect("editar_propiedad", prop_id=doc.propiedad.id)

    return redirect("editar_propiedad", prop_id=doc.propiedad.id)


@login_required
def eliminar_documento_legal(request, doc_id):
    """Elimina un documento legal."""
    doc = get_object_or_404(LegalDocsProp, id=doc_id)

    if not _puede_editar_propiedad(request, doc.propiedad):
        messages.error(request, "No tienes permiso.")
        return redirect("detalle_propiedad", prop_id=doc.propiedad.id)

    if request.method == "POST":
        nombre = doc.nombre
        doc.delete()
        messages.success(request, f"🗑️ Documento '{nombre}' eliminado.")
        return redirect("editar_propiedad", prop_id=doc.propiedad.id)

    return redirect("editar_propiedad", prop_id=doc.propiedad.id)


# ================================================================
# HELPERS
# ================================================================

def _notificar(recipient, emitter, source_type, title, message, property_id=None, related_object_id=None):
    return Communication.objects.create(
        recipient=recipient,
        emitter_user=emitter,
        source_type=source_type,
        title=title,
        message=message,
        property_id=property_id,
        related_object_id=related_object_id,
    )


def _calcular_total(tipo_accion, meses, es_destacada=False):
    config = ConfiguracionPagoPubli.objects.filter(activo=True).first()
    if not config:
        return 0
    if es_destacada:
        if tipo_accion == "venta":
            return config.valor_destacado_venta_mensual * meses
        elif tipo_accion == "arriendo":
            return config.valor_destacado_arriendo_mensual * meses
        else:
            return config.valor_destacado_str_dia * meses
    else:
        if tipo_accion == "venta":
            return config.valor_pub_venta_mensual * meses
        elif tipo_accion == "arriendo":
            return config.valor_pub_arriendo_mensual * meses
        else:
            return config.valor_pub_str_dia * meses


def _get_corredor_propiedad(propiedad):
    """Obtiene el primer corredor activo asignado a una propiedad."""
    cp = CorredorProp.objects.filter(
        propiedad=propiedad, estado="activa"
    ).select_related("corredor").first()
    return cp.corredor if cp else None


def _puede_gestionar_proceso(request, proceso):
    """Verifica si el usuario puede gestionar un proceso de compra."""
    es_corredor = request.user == proceso.corredor
    es_admin = request.user.rol in ("gerente", "superadmin")
    return es_corredor or es_admin


def _puede_ver_proceso(request, proceso):
    """Verifica si el usuario puede ver un proceso."""
    es_corredor = request.user == proceso.corredor
    es_admin = request.user.rol in ("gerente", "superadmin")
    es_comprador = request.user == proceso.comprador
    es_vendedor = request.user == proceso.vendedor
    return es_corredor or es_admin or es_comprador or es_vendedor


# ================================================================
# CIERRE ECONÓMICO AUTOMÁTICO
# ================================================================

def _get_plan_corredor(corredor):
    """Obtiene plan y tasa SERCA del corredor."""
    plan_nombre = ""
    tasa_serca = Decimal('0')
    try:
        if hasattr(corredor, 'plan') and corredor.plan:
            plan_nombre = corredor.plan.nombre if hasattr(corredor.plan, 'nombre') else str(corredor.plan)
            tasa_serca = corredor.plan.tasa_serca if hasattr(corredor.plan, 'tasa_serca') else Decimal('0')
    except Exception:
        pass
    return plan_nombre, tasa_serca


def _calcular_comision_clp(precio, tipo, valor):
    """Calcula comisión en CLP según tipo (porcentaje o fijo)."""
    if not precio or not valor:
        return Decimal('0')
    if tipo == "porcentaje":
        return Decimal(str(precio)) * Decimal(str(valor)) / Decimal('100')
    return Decimal(str(valor))  # monto fijo


def _crear_cierre_automatico(propiedad, corredor, tipo_cierre, precio=None, moneda=None,
                               tipo_comision_vendedor=None, valor_comision_vendedor=None,
                               tipo_comision_comprador=None, valor_comision_comprador=None,
                               fecha_cierre=None):
    """
    Crea un CierreEconomico automáticamente al cerrar un caso.
    Si ya existe uno para el mismo mes/año, no lo duplica.
    """
    if fecha_cierre is None:
        fecha_cierre = timezone.now()

    if precio is None:
        precio = propiedad.precio
    if moneda is None:
        moneda = propiedad.tipo_moneda

    # Fallback a CorredorProp si faltan datos de comisión
    cp = propiedad.corredores.filter(estado="activa").first()
    if tipo_comision_vendedor is None and cp:
        tipo_comision_vendedor = cp.tipo_comision
        valor_comision_vendedor = cp.monto_comision_dueno
    if tipo_comision_comprador is None and cp:
        tipo_comision_comprador = cp.tipo_comision
        valor_comision_comprador = cp.monto_comision_usu

    # Plan del corredor
    plan_nombre, tasa_serca = _get_plan_corredor(corredor)

    # Calcular comisiones presupuestadas
    comision_vendedor = _calcular_comision_clp(precio, tipo_comision_vendedor, valor_comision_vendedor)
    comision_comprador = _calcular_comision_clp(precio, tipo_comision_comprador, valor_comision_comprador)

    # % reference
    pct_v = Decimal(str(valor_comision_vendedor)) if tipo_comision_vendedor == "porcentaje" and valor_comision_vendedor else Decimal('0')
    pct_c = Decimal(str(valor_comision_comprador)) if tipo_comision_comprador == "porcentaje" and valor_comision_comprador else Decimal('0')

    mes = fecha_cierre.month
    anio = fecha_cierre.year

    cierre, created = CierreEconomico.objects.get_or_create(
        propiedad=propiedad,
        corredor=corredor,
        mes=mes,
        anio=anio,
        defaults={
            'precio_venta': precio,
            'moneda_original': moneda,
            'pct_comision_vendedor': pct_v,
            'pct_comision_comprador': pct_c,
            'comision_vendedor_presupuestada_clp': comision_vendedor,
            'comision_comprador_presupuestada_clp': comision_comprador,
            'plan_nombre': plan_nombre,
            'tasa_serca': tasa_serca,
            'fecha_cierre': fecha_cierre,
            'perfeccionado': False,
        }
    )
    if created:
        # Notificar a gerentes
        gerentes = User.objects.filter(rol__in=["gerente", "superadmin"], is_active=True)
        for g in gerentes:
            _notificar(
                recipient=g,
                emitter=corredor,
                source_type=SourceTypeChoices.CORREDOR,
                title="💰 Nuevo cierre económico pendiente",
                message=(
                    f"Se ha creado un Cierre Económico pendiente de perfeccionar para "
                    f"{propiedad.display_name_public()} ({tipo_cierre}). "
                    f"Monto base: ${float(comision_vendedor + comision_comprador):,.0f} CLP."
                    f"\n→ Revisa en Gestión de Ingresos."
                ),
                property_id=propiedad.id,
            )
        logger.info(f"CierreEconomico #{cierre.id} creado automáticamente para propiedad #{propiedad.id}")
    return cierre


# ================================================================
# FLUJO DE SOLICITUD DE PUBLICACIÓN (5 PASOS)
# ================================================================

@login_required
def solicitar_publicacion(request):
    """Paso 1: usuario sube datos básicos, fotos, pago"""
    config_pago = ConfiguracionPagoPubli.objects.filter(activo=True).first()
    comunas = Comuna.objects.all().order_by("nombre")
    regiones = Region.objects.all()

    if request.method == "POST":
        calle = request.POST.get("calle", "").strip()
        numero_calle = request.POST.get("numero_calle", "").strip()
        tipo_prop = request.POST.get("tipo_prop", "")
        comuna_id = request.POST.get("comuna")
        region_id = request.POST.get("region")
        numero_dormitorios = request.POST.get("numero_dormitorios", 0)
        numero_banos = request.POST.get("numero_banos", 0)
        m_construidos = request.POST.get("m_construidos")
        m_terreno = request.POST.get("m_terreno")
        num_estacionamientos = request.POST.get("num_estacionamientos", 0)
        tiene_bodega = request.POST.get("tiene_bodega") == "1"
        num_tipo_prop = request.POST.get("num_tipo_prop", "")

        meses = int(request.POST.get("meses", 1))
        es_destacada = request.POST.get("es_destacada") == "1"

        fotos = request.FILES.getlist("fotos")
        if len(fotos) < 1:
            messages.error(request, "Debes subir al menos 1 foto de la propiedad.")
            return render(request, "solicitar_publicacion.html", {
                "config_pago": config_pago,
                "comunas": comunas,
                "regiones": regiones,
            })

        comprobante = request.FILES.get("comprobante")
        if not comprobante:
            messages.error(request, "Debes subir el comprobante de pago.")
            return render(request, "solicitar_publicacion.html", {
                "config_pago": config_pago,
                "comunas": comunas,
                "regiones": regiones,
            })

        total = _calcular_total(request.POST.get("tipo_accion", "venta"), meses, es_destacada)

        propiedad = Propiedad.objects.create(
            dueno=request.user,
            calle=calle,
            numero_calle=numero_calle,
            tipo_prop=tipo_prop,
            num_tipo_prop=num_tipo_prop,
            comuna_id=comuna_id or None,
            region_id=region_id or None,
            numero_dormitorios=numero_dormitorios,
            numero_banos=numero_banos,
            m_construidos=m_construidos or None,
            m_terreno=m_terreno or None,
            tiene_bodega=tiene_bodega,
            num_estacionamientos=num_estacionamientos,
            tipo_accion=request.POST.get("tipo_accion", "venta"),
            tipo_moneda=request.POST.get("tipo_moneda", "PCL"),
            precio=request.POST.get("precio", 0),
            estado="borrador",
        )

        for f in fotos:
            FotosPropiedad.objects.create(propiedad=propiedad, imagen=f)

        solicitud = SolicitudPublicacion.objects.create(
            usuario=request.user,
            meses=meses,
            es_destacada=es_destacada,
            total_pago=total,
            comprobante=comprobante,
            propiedad=propiedad,
            estado="pago_revision",
        )

        gerentes = User.objects.filter(rol__in=["gerente", "superadmin"], is_active=True)
        for g in gerentes:
            _notificar(
                recipient=g,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="Nueva solicitud de publicación",
                message=(
                    f"El usuario {request.user.get_full_name() or request.user.email} "
                    f"ha solicitado publicar {propiedad.display_name_public()}. "
                    f"{'⭐ Destacada' if es_destacada else 'Normal'} · {meses} meses. "
                    f"Total: ${total:,.0f}."
                ),
                related_object_id=solicitud.id,
            )

        messages.success(request, "¡Solicitud enviada! Un gerente revisará tu pago.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    return render(request, "solicitar_publicacion.html", {
        "config_pago": config_pago,
        "comunas": comunas,
        "regiones": regiones,
    })


@login_required
def detalle_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if not (
        request.user == solicitud.usuario
        or request.user == solicitud.corredor_asignado
        or request.user.rol in ("gerente", "superadmin")
    ):
        messages.error(request, "No tienes permiso para ver esta solicitud.")
        return redirect("gestion")

    observaciones = solicitud.observaciones.all().select_related("autor")
    servicios = ServiciosProp.objects.filter(is_active=True)
    comunas = Comuna.objects.all().order_by("nombre")
    regiones = Region.objects.all()
    config_pago = ConfiguracionPagoPubli.objects.filter(activo=True).first()
    corredores_disponibles = User.objects.filter(
        rol__in=("corredor", "gerente", "superadmin"), is_active=True
    )

    # --- Orientación de documentos legales según tipo de acción ---
    if solicitud.propiedad:
        tipo_accion = solicitud.propiedad.tipo_accion
    else:
        # Fallback: si no hay propiedad asociada (Solicitud #6 o similar),
        # mostramos la orientación más completa (venta) como referencia
        tipo_accion = "venta"
    docs_orientacion_texto = _get_docs_orientacion_texto(tipo_accion)

    return render(request, "detalle_solicitud.html", {
        "solicitud": solicitud,
        "observaciones": observaciones,
        "servicios": servicios,
        "comunas": comunas,
        "regiones": regiones,
        "config_pago": config_pago,
        "corredores_disponibles": corredores_disponibles,
        "docs_orientacion_texto": docs_orientacion_texto,
    })


@login_required
def agregar_observacion(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    es_autor = request.user == solicitud.usuario
    es_gerente = request.user.rol in ("gerente", "superadmin")
    es_corredor = request.user == solicitud.corredor_asignado

    if not (es_autor or es_gerente or es_corredor):
        messages.error(request, "No tienes permiso.")
        return redirect("gestion")

    if request.method == "POST":
        texto = request.POST.get("texto", "").strip()
        archivo = request.FILES.get("archivo")
        if not texto and not archivo:
            messages.error(request, "Debes escribir un mensaje o adjuntar un archivo.")
            return redirect("detalle_solicitud", solicitud_id=solicitud.id)

        ObservacionSolicitud.objects.create(
            solicitud=solicitud,
            autor=request.user,
            texto=texto,
            archivo=archivo,
        )

        if es_gerente or es_corredor:
            _notificar(
                recipient=solicitud.usuario,
                emitter=request.user,
                source_type=SourceTypeChoices.GERENTE if es_gerente else SourceTypeChoices.CORREDOR,
                title=f"Nueva observación en solicitud #{solicitud.id}",
                message=f"Han agregado una observación a tu solicitud: {texto[:200]}",
                related_object_id=solicitud.id,
            )
        else:
            admins = User.objects.filter(rol__in=["gerente", "superadmin"], is_active=True)
            for a in admins:
                _notificar(
                    recipient=a,
                    emitter=request.user,
                    source_type=SourceTypeChoices.USUARIO_BASE,
                    title=f"Nueva observación del usuario en solicitud #{solicitud.id}",
                    message=f"El usuario respondió: {texto[:200]}",
                    related_object_id=solicitud.id,
                )
            if solicitud.corredor_asignado:
                _notificar(
                    recipient=solicitud.corredor_asignado,
                    emitter=request.user,
                    source_type=SourceTypeChoices.USUARIO_BASE,
                    title=f"Nueva observación del usuario en solicitud #{solicitud.id}",
                    message=f"El usuario respondió: {texto[:200]}",
                    related_object_id=solicitud.id,
                )

        messages.success(request, "Observación agregada correctamente.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    return redirect("detalle_solicitud", solicitud_id=solicitud.id)


@login_required
def aprobar_pago_solicitud(request, solicitud_id):
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos.")
        return redirect("gestion")

    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)
    if solicitud.estado not in ("pago_revision", "pago_objetado"):
        messages.error(request, "Esta solicitud no está en revisión de pago.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    corredor_id = request.POST.get("corredor_id", "").strip()

    if corredor_id:
        # Aprobar pago y asignar corredor en un solo paso
        try:
            corredor = User.objects.get(
                id=corredor_id,
                rol__in=("corredor", "gerente", "superadmin"),
                is_active=True,
            )
        except User.DoesNotExist:
            messages.error(
                request,
                "El corredor seleccionado no es válido. Vuelve a intentarlo.",
            )
            return redirect("detalle_solicitud", solicitud_id=solicitud.id)

        solicitud.corredor_asignado = corredor
        solicitud.estado = "en_revision_corredor"
        solicitud.save()

        if solicitud.propiedad:
            CorredorProp.objects.get_or_create(
                propiedad=solicitud.propiedad,
                corredor=corredor,
                defaults={"tipo_comision": "porcentaje", "estado": "activa"},
            )

        _notificar(
            recipient=solicitud.usuario,
            emitter=request.user,
            source_type=SourceTypeChoices.GERENTE,
            title="Pago aprobado y corredor asignado",
            message=(
                f"¡Tu pago por ${solicitud.total_pago:,.0f} ha sido aprobado! "
                f"Se asignó a {corredor.get_full_name() or corredor.email} para gestionar tu publicación."
            ),
            related_object_id=solicitud.id,
        )

        _notificar(
            recipient=corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.GERENTE,
            title="Nueva solicitud asignada",
            message=(
                f"Se te ha asignado la solicitud #{solicitud.id} del usuario "
                f"{solicitud.usuario.get_full_name() or solicitud.usuario.email}. "
                f"Debes subir la Orden de Gestión."
            ),
            related_object_id=solicitud.id,
        )

        messages.success(
            request,
            f"Pago aprobado y corredor {corredor.get_full_name() or corredor.email} asignado.",
        )
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    # Sin corredor seleccionado: solo aprobar pago
    solicitud.estado = "pago_aprobado"
    solicitud.save()

    _notificar(
        recipient=solicitud.usuario,
        emitter=request.user,
        source_type=SourceTypeChoices.GERENTE,
        title="Pago aprobado",
        message=f"¡Tu pago por ${solicitud.total_pago:,.0f} ha sido aprobado! Ahora se asignará un corredor.",
        related_object_id=solicitud.id,
    )

    messages.success(request, "Pago aprobado. Ahora asigna un corredor.")
    return redirect("detalle_solicitud", solicitud_id=solicitud.id)


@login_required
def rechazar_pago_solicitud(request, solicitud_id):
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos.")
        return redirect("gestion")

    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)
    if solicitud.estado not in ("pago_revision", "pago_objetado"):
        messages.error(request, "Estado inválido.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    razon = request.POST.get("razon", "").strip()
    if not razon:
        messages.error(request, "Debes indicar una razón para el rechazo.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    solicitud.estado = "pago_objetado"
    solicitud.save()

    ObservacionSolicitud.objects.create(
        solicitud=solicitud,
        autor=request.user,
        texto=f"Pago rechazado: {razon}",
    )

    _notificar(
        recipient=solicitud.usuario,
        emitter=request.user,
        source_type=SourceTypeChoices.GERENTE,
        title="Pago objetado",
        message=f"Tu pago ha sido objetado. Razón: {razon}. Revisa las observaciones y corrige.",
        related_object_id=solicitud.id,
    )

    messages.warning(request, "Pago rechazado. Se notificó al usuario.")
    return redirect("detalle_solicitud", solicitud_id=solicitud.id)


@login_required
def asignar_corredor_solicitud(request, solicitud_id):
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permisos.")
        return redirect("gestion")

    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if solicitud.estado not in ("pago_aprobado", "esperando_corredor"):
        messages.error(request, "Esta solicitud no está esperando corredor.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    if request.method == "POST":
        corredor_id = request.POST.get("corredor_id")
        if not corredor_id:
            messages.error(request, "Debes seleccionar un corredor.")
            return redirect("detalle_solicitud", solicitud_id=solicitud.id)

        corredor = get_object_or_404(
            User,
            id=corredor_id,
            rol__in=("corredor", "gerente", "superadmin"),
            is_active=True,
        )
        solicitud.corredor_asignado = corredor
        solicitud.estado = "en_revision_corredor"
        solicitud.save()

        if solicitud.propiedad:
            CorredorProp.objects.get_or_create(
                propiedad=solicitud.propiedad,
                corredor=corredor,
                defaults={"tipo_comision": "porcentaje", "estado": "activa"},
            )

        _notificar(
            recipient=corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.GERENTE,
            title="Nueva solicitud asignada",
            message=f"Se te ha asignado la solicitud #{solicitud.id} del usuario {solicitud.usuario.get_full_name() or solicitud.usuario.email}. Debes subir la Orden de Gestión.",
            related_object_id=solicitud.id,
        )

        _notificar(
            recipient=solicitud.usuario,
            emitter=request.user,
            source_type=SourceTypeChoices.GERENTE,
            title="Corredor asignado",
            message="Se ha asignado un corredor a tu solicitud. Él subirá la Orden de Gestión.",
            related_object_id=solicitud.id,
        )

        messages.success(request, f"Corredor {corredor.get_full_name()} asignado.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    return redirect("detalle_solicitud", solicitud_id=solicitud.id)


@login_required
def subir_orden_gestion(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if request.user != solicitud.corredor_asignado:
        messages.error(request, "Solo el corredor asignado puede subir la Orden de Gestión.")
        return redirect("gestion")

    if solicitud.estado not in ("en_revision_corredor", "og_pendiente"):
        messages.error(request, f"No puedes subir OG en estado {solicitud.get_estado_display()}.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    if request.method == "POST":
        og = request.FILES.get("orden_gestion")
        if not og:
            messages.error(request, "Debes seleccionar un archivo PDF.")
            return redirect("detalle_solicitud", solicitud_id=solicitud.id)

        docs_requeridos = request.POST.get("docs_requeridos", "").strip()

        solicitud.orden_gestion = og
        solicitud.docs_requeridos = docs_requeridos
        solicitud.estado = "og_pendiente"
        solicitud.save()

        _notificar(
            recipient=solicitud.usuario,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="Orden de Gestión lista para revisar",
            message="El corredor ha subido la Orden de Gestión. Revísala, acéptala y completa los datos faltantes.",
            related_object_id=solicitud.id,
        )

        messages.success(request, "Orden de Gestión subida. El usuario debe aceptarla y completar datos.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    return redirect("detalle_solicitud", solicitud_id=solicitud.id)


@login_required
def aceptar_orden_gestion(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if request.user != solicitud.usuario:
        messages.error(request, "Solo el solicitante puede aceptar la Orden de Gestión.")
        return redirect("gestion")

    if solicitud.estado != "og_pendiente":
        messages.error(request, "No hay Orden de Gestión pendiente.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    if not solicitud.orden_gestion:
        messages.error(request, "El corredor aún no ha subido la Orden de Gestión.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    if request.method == "POST":
        acepta = request.POST.get("acepta") == "on"
        if not acepta:
            messages.error(request, "Debes marcar que aceptas las condiciones.")
            return redirect("detalle_solicitud", solicitud_id=solicitud.id)

        solicitud.og_aceptada = True
        solicitud.og_aceptada_at = timezone.now()
        solicitud.estado = "og_aceptada"
        solicitud.save()

        _notificar(
            recipient=solicitud.corredor_asignado,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="Orden de Gestión aceptada",
            message="El usuario aceptó la OG. Ahora debe completar los datos de la propiedad.",
            related_object_id=solicitud.id,
        )

        messages.success(request, "¡OG aceptada! Ahora completa los datos de tu propiedad.")
        return redirect("completar_datos_propiedad", solicitud_id=solicitud.id)

    return redirect("detalle_solicitud", solicitud_id=solicitud.id)


@login_required
def completar_datos_propiedad(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if request.user != solicitud.usuario:
        messages.error(request, "Solo el solicitante puede completar los datos.")
        return redirect("gestion")

    if solicitud.estado not in ("og_aceptada", "en_validacion", "og_pendiente"):
        messages.error(request, f"No puedes completar datos en estado {solicitud.get_estado_display()}.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    propiedad = solicitud.propiedad
    if not propiedad:
        messages.error(request, "La propiedad no está registrada.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    servicios = ServiciosProp.objects.filter(is_active=True)
    comunas = Comuna.objects.all().order_by("nombre")
    regiones = Region.objects.all()

    docs_requeridos_lista = [d.strip() for d in solicitud.docs_requeridos.split(",") if d.strip()]

    if request.method == "POST":
        propiedad.descripcion_propiedad = request.POST.get("descripcion_propiedad", "")
        propiedad.descripcion_entorno = request.POST.get("descripcion_entorno", "")
        propiedad.precio = request.POST.get("precio", propiedad.precio)
        propiedad.tipo_moneda = request.POST.get("tipo_moneda", propiedad.tipo_moneda)
        propiedad.montomensual_gastoscomunes_pcl = request.POST.get("montomensual_gastoscomunes_pcl") or None
        propiedad.montoanual_contribuciones_pcl = request.POST.get("montoanual_contribuciones_pcl") or None
        propiedad.save()

        servicios_ids = request.POST.getlist("servicios")
        if servicios_ids:
            propiedad.servicios_prop.set(servicios_ids)
        else:
            propiedad.servicios_prop.clear()

        docs_files = request.FILES.getlist("documentos")
        docs_nombres = request.POST.getlist("doc_nombres")
        for i, doc in enumerate(docs_files):
            nombre_doc = docs_nombres[i] if i < len(docs_nombres) and docs_nombres[i].strip() else doc.name
            LegalDocsProp.objects.create(
                propiedad=propiedad,
                nombre=nombre_doc,
                documento=doc,
                estado="pendiente",
            )

        fotos = request.FILES.getlist("fotos")
        for f in fotos:
            FotosPropiedad.objects.create(propiedad=propiedad, imagen=f)

        if solicitud.estado == "og_aceptada":
            solicitud.estado = "en_validacion"
            solicitud.save()

        _notificar(
            recipient=solicitud.corredor_asignado,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="Datos completados - Revisión pendiente",
            message="El usuario ha completado todos los datos de la propiedad. Revisa y valida.",
            related_object_id=solicitud.id,
        )

        messages.success(request, "Datos guardados. El corredor revisará y validará la información.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    fotos_existentes = propiedad.fotos.all()
    max_fotos = 10 if solicitud.es_destacada else 3

    return render(request, "completar_datos_propiedad.html", {
        "solicitud": solicitud,
        "propiedad": propiedad,
        "servicios": servicios,
        "comunas": comunas,
        "regiones": regiones,
        "docs_requeridos_lista": docs_requeridos_lista,
        "fotos_existentes": fotos_existentes,
        "max_fotos": max_fotos,
    })


@login_required
def validar_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if request.user != solicitud.corredor_asignado:
        messages.error(request, "Solo el corredor asignado puede validar.")
        return redirect("gestion")

    if solicitud.estado not in ("en_validacion",):
        messages.error(request, f"No puedes validar en estado {solicitud.get_estado_display()}.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    if request.method == "POST":
        accion = request.POST.get("accion")
        texto = request.POST.get("texto", "").strip()

        if accion == "aprobar":
            return redirect("publicar_solicitud", solicitud_id=solicitud.id)

        elif accion == "rechazar":
            if not texto:
                messages.error(request, "Debes indicar qué corregir.")
                return redirect("detalle_solicitud", solicitud_id=solicitud.id)

            ObservacionSolicitud.objects.create(
                solicitud=solicitud,
                autor=request.user,
                texto=f"Correcciones solicitadas: {texto}",
                archivo=request.FILES.get("archivo"),
            )

            solicitud.estado = "og_aceptada"
            solicitud.save()

            _notificar(
                recipient=solicitud.usuario,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR,
                title="Correcciones solicitadas",
                message=f"El corredor solicita correcciones: {texto[:200]}",
                related_object_id=solicitud.id,
            )

            messages.warning(request, "Se solicitaron correcciones. Se notificó al usuario.")
            return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    return redirect("detalle_solicitud", solicitud_id=solicitud.id)


@login_required
def publicar_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if request.user != solicitud.corredor_asignado:
        messages.error(request, "Solo el corredor asignado puede publicar.")
        return redirect("gestion")

    if solicitud.estado not in ("en_validacion",):
        messages.error(request, "Debes aprobar la validación antes de publicar.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    propiedad = solicitud.propiedad
    if not propiedad:
        messages.error(request, "La propiedad no está registrada.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    if not propiedad.fotos.exists():
        messages.error(request, "La propiedad debe tener al menos una foto.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    pub = PublicacionProp.objects.create(
        propiedad=propiedad,
        publicante=solicitud.usuario,
        meses=solicitud.meses,
        es_destacada=solicitud.es_destacada,
        total_pago=solicitud.total_pago,
        comprobante=solicitud.comprobante,
        estado="publicada",
        inicia_at=timezone.now(),
        expira_at=timezone.now() + timezone.timedelta(days=30 * solicitud.meses),
    )

    propiedad.estado = "publicada"
    propiedad.save()

    solicitud.estado = "publicada"
    solicitud.save()

    _notificar(
        recipient=solicitud.usuario,
        emitter=request.user,
        source_type=SourceTypeChoices.CORREDOR,
        title="¡Propiedad publicada!",
        message=f"Tu propiedad {propiedad.display_name_public()} ha sido publicada exitosamente.",
        property_id=propiedad.id,
        related_object_id=solicitud.id,
    )

    messages.success(request, f"¡Propiedad publicada! {pub.dias_restantes} días restantes.")
    return redirect("detalle_propiedad", prop_id=propiedad.id)


@login_required
def subir_fotos_propiedad(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if request.user != solicitud.usuario:
        messages.error(request, "No tienes permiso.")
        return redirect("gestion")

    if not solicitud.propiedad:
        messages.error(request, "La propiedad no está registrada.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    if request.method == "POST":
        fotos = request.FILES.getlist("fotos")
        if not fotos:
            messages.error(request, "Debes seleccionar al menos una foto.")
            return redirect("detalle_solicitud", solicitud_id=solicitud.id)

        for f in fotos:
            FotosPropiedad.objects.create(propiedad=solicitud.propiedad, imagen=f)

        messages.success(request, f"{len(fotos)} foto(s) subida(s).")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    return redirect("detalle_solicitud", solicitud_id=solicitud.id)


@login_required
def cancelar_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudPublicacion, id=solicitud_id)

    if not (request.user == solicitud.usuario or request.user.rol in ("gerente", "superadmin")):
        messages.error(request, "No tienes permiso.")
        return redirect("gestion")

    if solicitud.estado in ("publicada", "rechazada", "cancelada"):
        messages.error(request, "Esta solicitud ya está finalizada.")
        return redirect("detalle_solicitud", solicitud_id=solicitud.id)

    solicitud.estado = "cancelada"
    solicitud.save()

    messages.success(request, "Solicitud cancelada.")
    return redirect("gestion")


# ================================================================
# SOLICITUD DE VISITA
# ================================================================

@login_required
def agenda_disponible_api(request, prop_id):
    """API JSON: retorna los bloques de agenda disponibles."""
    propiedad = get_object_or_404(Propiedad, id=prop_id)
    corredor = _get_corredor_propiedad(propiedad)
    if not corredor:
        return JsonResponse({"error": "Esta propiedad no tiene corredor asignado."}, status=400)

    ahora = timezone.localtime()
    hoy = ahora.date()
    hora_actual = ahora.time()

    bloques = AgendaCorredor.objects.filter(
        corredor=corredor,
        activo=True,
        reservado=False,
        fecha__gte=hoy,
    ).order_by("fecha", "hora_inicio")

    data = []
    for b in bloques:
        if b.fecha == hoy and b.hora_inicio <= hora_actual:
            continue
        data.append({
            "id": b.id,
            "fecha": b.fecha.isoformat(),
            "hora_inicio": b.hora_inicio.strftime("%H:%M"),
            "hora_fin": b.hora_fin.strftime("%H:%M"),
            "etiqueta": f"{b.fecha.strftime('%d/%m/%Y')} {b.hora_inicio.strftime('%H:%M')} - {b.hora_fin.strftime('%H:%M')}",
        })

    return JsonResponse({"bloques": data, "corredor": {
        "id": corredor.id,
        "nombre": corredor.get_full_name() or corredor.username,
    }})


@login_required
def solicitar_visita(request, prop_id):
    """Solicita una visita seleccionando un bloque de agenda."""
    propiedad = get_object_or_404(Propiedad, id=prop_id)

    if request.user == propiedad.dueno:
        messages.error(request, "No puedes solicitar visita a tu propia propiedad.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    corredor = _get_corredor_propiedad(propiedad)
    if not corredor:
        messages.error(request, "Esta propiedad aún no tiene un corredor asignado.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    # Verificar que el usuario no tenga ya una visita pendiente/aceptada
    visita_existente = SolicitudVisita.objects.filter(
        usuario=request.user,
        propiedad=propiedad,
        estado__in=["pendiente", "aceptada", "realizada"],
    ).exists()
    if visita_existente:
        messages.warning(request, "Ya tienes una solicitud de visita activa para esta propiedad.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    # Verificar si el proceso está pausado
    proceso_activo = ProcesoCompra.objects.filter(
        propiedad=propiedad,
        estado__in=[
            "promesa_aceptada", "instrucciones_aceptada",
            "contrato_pendiente", "contrato_listo", "firma_notarial",
            "escritura_cbr",
        ],
    ).exists()
    if proceso_activo:
        messages.error(request, "Esta propiedad está en proceso de compra con otro comprador. No se pueden solicitar nuevas visitas por ahora.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    if request.method == "POST":
        bloque_id = request.POST.get("bloque_agenda_id")
        if not bloque_id:
            messages.error(request, "Debes seleccionar un horario disponible.")
            return redirect("detalle_propiedad", prop_id=prop_id)

        bloque = get_object_or_404(AgendaCorredor, id=bloque_id, activo=True)

        if bloque.reservado:
            messages.error(request, "Este horario ya no está disponible.")
            return redirect("detalle_propiedad", prop_id=prop_id)

        if bloque.fecha < timezone.localdate():
            messages.error(request, "No puedes agendar en una fecha pasada.")
            return redirect("detalle_propiedad", prop_id=prop_id)

        bloque.reservado = True
        bloque.save()

        visita = SolicitudVisita.objects.create(
            usuario=request.user,
            propiedad=propiedad,
            corredor=corredor,
            bloque_agenda=bloque,
            fecha_solicitada=bloque.fecha,
            hora_inicio_solicitada=bloque.hora_inicio,
            hora_fin_solicitada=bloque.hora_fin,
            estado="pendiente",
        )

        _notificar(
            recipient=corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="Nueva solicitud de visita",
            message=f"{request.user.get_full_name() or request.user.email} ha solicitado visitar {propiedad.display_name_public()} el {bloque.fecha.strftime('%d/%m/%Y')} a las {bloque.hora_inicio.strftime('%H:%M')}.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        _notificar(
            recipient=propiedad.dueno,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="Solicitud de visita a tu propiedad",
            message=f"{request.user.get_full_name() or request.user.email} ha solicitado visitar tu propiedad {propiedad.display_name_public()}.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        messages.success(request, "¡Solicitud de visita enviada! El corredor confirmará la hora.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    return redirect("detalle_propiedad", prop_id=prop_id)


@login_required
def subir_orden_visita(request, visita_id):
    """Corredor adjunta PDF Orden de Visita."""
    visita = get_object_or_404(SolicitudVisita, id=visita_id)

    es_corredor_asignado = request.user == visita.corredor
    es_gerente = request.user.rol in ("gerente", "superadmin")

    if not (es_corredor_asignado or es_gerente):
        messages.error(request, "Solo el corredor asignado puede subir la Orden de Visita.")
        return redirect("gestion")

    if visita.estado not in ("pendiente", "aceptada"):
        messages.error(request, f"No puedes subir OV en estado {visita.get_estado_display()}.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if request.method == "POST":
        pdf = request.FILES.get("orden_visita")
        if not pdf:
            messages.error(request, "Debes seleccionar un archivo PDF.")
            return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

        visita.orden_visita = pdf
        visita.orden_visita_subida_por = request.user
        visita.save()

        _notificar(
            recipient=visita.usuario,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR if es_corredor_asignado else SourceTypeChoices.GERENTE,
            title="Orden de Visita lista",
            message=f"El corredor ha subido la Orden de Visita para la propiedad {visita.propiedad.display_name_public()}. Revisa y acepta las cláusulas para formalizar la visita.",
            property_id=visita.propiedad.id,
            related_object_id=visita.id,
        )

        messages.success(request, "Orden de Visita subida. El usuario debe aceptar las cláusulas.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    return redirect("detalle_propiedad", prop_id=visita.propiedad.id)


@login_required
def aceptar_orden_visita(request, visita_id):
    """Usuario acepta las cláusulas de la Orden de Visita."""
    visita = get_object_or_404(SolicitudVisita, id=visita_id)

    if request.user != visita.usuario:
        messages.error(request, "Solo el solicitante puede aceptar la Orden de Visita.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if not visita.orden_visita:
        messages.error(request, "El corredor aún no ha subido la Orden de Visita.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if visita.clausulas_aceptadas:
        messages.warning(request, "Ya aceptaste las cláusulas anteriormente.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if visita.estado not in ("pendiente", "aceptada"):
        messages.error(request, f"No puedes aceptar en estado {visita.get_estado_display()}.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if request.method == "POST":
        acepta = request.POST.get("acepta") == "on"
        if not acepta:
            messages.error(request, "Debes marcar que aceptas las cláusulas de la Orden de Visita.")
            return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

        visita.clausulas_aceptadas = True
        visita.clausulas_aceptadas_at = timezone.now()
        visita.estado = "aceptada"
        visita.save()

        _notificar(
            recipient=visita.corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="Orden de Visita aceptada",
            message=f"{request.user.get_full_name() or request.user.email} aceptó las cláusulas de la Orden de Visita para {visita.propiedad.display_name_public()}.",
            property_id=visita.propiedad.id,
            related_object_id=visita.id,
        )

        messages.success(request, "¡Cláusulas aceptadas! Visita formalizada.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    return redirect("detalle_propiedad", prop_id=visita.propiedad.id)


@login_required
def gestionar_solicitud_visita(request, visita_id):
    """Corredor/gerente gestiona solicitud: aceptar, rechazar, reprogramar."""
    visita = get_object_or_404(SolicitudVisita, id=visita_id)

    es_corredor = request.user == visita.corredor
    es_admin = request.user.rol in ("gerente", "superadmin")

    if not (es_corredor or es_admin):
        messages.error(request, "No tienes permiso para gestionar esta solicitud.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if visita.estado not in ("pendiente", "reprogramada"):
        messages.error(request, f"No puedes gestionar en estado {visita.get_estado_display()}.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "aceptar":
            visita.estado = "aceptada"
            visita.save()

            _notificar(
                recipient=visita.usuario,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
                title="Visita confirmada",
                message=f"Tu visita a {visita.propiedad.display_name_public()} el {visita.fecha_solicitada.strftime('%d/%m/%Y')} a las {visita.hora_inicio_solicitada.strftime('%H:%M')} ha sido confirmada.",
                property_id=visita.propiedad.id,
                related_object_id=visita.id,
            )

            messages.success(request, "Visita aceptada.")
            return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

        elif accion == "rechazar":
            razon = request.POST.get("razon", "").strip()
            if not razon:
                messages.error(request, "Debes indicar una razón para el rechazo.")
                return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

            if visita.bloque_agenda:
                visita.bloque_agenda.reservado = False
                visita.bloque_agenda.save()

            visita.estado = "rechazada"
            visita.motivo_rechazo = razon
            visita.save()

            _notificar(
                recipient=visita.usuario,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
                title="Visita rechazada",
                message=f"Tu solicitud de visita para {visita.propiedad.display_name_public()} ha sido rechazada. Razón: {razon}.",
                property_id=visita.propiedad.id,
                related_object_id=visita.id,
            )

            messages.warning(request, "Visita rechazada.")
            return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

        elif accion == "reprogramar":
            nueva_fecha = request.POST.get("nueva_fecha", "").strip()
            nueva_hora_inicio = request.POST.get("nueva_hora_inicio", "").strip()
            nueva_hora_fin = request.POST.get("nueva_hora_fin", "").strip()
            mensaje = request.POST.get("mensaje", "").strip()

            if not (nueva_fecha and nueva_hora_inicio and nueva_hora_fin):
                messages.error(request, "Debes indicar fecha, hora inicio y hora fin.")
                return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

            from datetime import datetime as dt
            visita.fecha_reprogramada = dt.strptime(nueva_fecha, "%Y-%m-%d").date()
            visita.hora_reprogramada_inicio = dt.strptime(nueva_hora_inicio, "%H:%M").time()
            visita.hora_reprogramada_fin = dt.strptime(nueva_hora_fin, "%H:%M").time()
            visita.mensaje_reprogramacion = mensaje
            visita.estado = "reprogramada"
            visita.save()

            _notificar(
                recipient=visita.usuario,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
                title="Propuesta de nueva fecha para visita",
                message=f"El corredor propone reprogramar tu visita a {visita.propiedad.display_name_public()} para el {visita.fecha_reprogramada.strftime('%d/%m/%Y')} a las {visita.hora_reprogramada_inicio.strftime('%H:%M')}. Mensaje: {mensaje[:200]}",
                property_id=visita.propiedad.id,
                related_object_id=visita.id,
            )

            messages.success(request, "Reprogramación propuesta. Esperando confirmación del usuario.")
            return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

        elif accion == "confirmar_reprogramacion":
            if request.user != visita.usuario:
                messages.error(request, "Solo el solicitante puede confirmar la reprogramación.")
                return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

            if visita.estado != "reprogramada":
                messages.error(request, "No hay reprogramación pendiente.")
                return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

            visita.fecha_solicitada = visita.fecha_reprogramada
            visita.hora_inicio_solicitada = visita.hora_reprogramada_inicio
            visita.hora_fin_solicitada = visita.hora_reprogramada_fin
            visita.fecha_reprogramada = None
            visita.hora_reprogramada_inicio = None
            visita.hora_reprogramada_fin = None
            visita.mensaje_reprogramacion = ""
            visita.estado = "pendiente"
            visita.save()

            _notificar(
                recipient=visita.corredor,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="Reprogramación confirmada",
                message=f"{request.user.get_full_name() or request.user.email} confirmó la nueva fecha para visitar {visita.propiedad.display_name_public()}: {visita.fecha_solicitada.strftime('%d/%m/%Y')} a las {visita.hora_inicio_solicitada.strftime('%H:%M')}.",
                property_id=visita.propiedad.id,
                related_object_id=visita.id,
            )

            messages.success(request, "¡Nueva fecha confirmada!")
            return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    return redirect("detalle_propiedad", prop_id=visita.propiedad.id)


@login_required
def marcar_visita_realizada(request, visita_id):
    """Corredor marca la visita como realizada."""
    visita = get_object_or_404(SolicitudVisita, id=visita_id)

    if request.user != visita.corredor and request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "Solo el corredor puede marcar la visita como realizada.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if visita.estado not in ("aceptada",):
        messages.error(request, f"No puedes marcar como realizada en estado {visita.get_estado_display()}.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if not visita.clausulas_aceptadas:
        messages.error(request, "El usuario aún no ha aceptado las cláusulas de la Orden de Visita.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if request.method == "POST":
        visita.estado = "realizada"
        visita.realizada_at = timezone.now()
        visita.save()

        _notificar(
            recipient=visita.usuario,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR if request.user == visita.corredor else SourceTypeChoices.GERENTE,
            title="Visita realizada - ¡Ahora puedes hacer una propuesta!",
            message=f"La visita a {visita.propiedad.display_name_public()} ha sido registrada como realizada. Si estás interesado, ya puedes hacer una propuesta de {'compra' if visita.propiedad.tipo_accion == 'venta' else 'arriendo'}.",
            property_id=visita.propiedad.id,
            related_object_id=visita.id,
        )

        # ===== EMAIL DE INCENTIVO A LA OFERTA =====
        # Además de la comunicación interna en el CDC, se envía un correo
        # desde "noreply" con el estilo gráfico de Serca para incentivar al
        # visitante a hacer una propuesta de compra/arriendo.
        try:
            propiedad = visita.propiedad
            tipo_accion = propiedad.tipo_accion
            tipo_accion_display = propiedad.get_tipo_accion_display()
            tipo_accion_texto = "compra" if tipo_accion == "venta" else "arriendo"

            sitio = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
            prop_url = f"https://{sitio}/prop/detalle/{propiedad.id}/"

            contexto_email = {
                "site_name": getattr(settings, "SITE_NAME", "Serca Propiedades"),
                "nombre_visitante": visita.usuario.get_full_name() or visita.usuario.username,
                "propiedad": propiedad,
                "tipo_accion_display": tipo_accion_display,
                "tipo_accion_texto": tipo_accion_texto,
                "prop_url": prop_url,
            }
            html_email = render_to_string("email/visita_realizada_oferta.html", contexto_email)
            texto_email = (
                f"Hola {contexto_email['nombre_visitante']},\n\n"
                f"Hemos registrado tu visita a la propiedad {propiedad.display_name_public()}.\n"
                f"Ahora puedes hacer una propuesta de {tipo_accion_texto}.\n\n"
                f"Para hacer tu oferta, abre: {prop_url}\n\n"
                f"Saludos,\nEl equipo de Serca Propiedades"
            )

            remitente_noreply = getattr(
                settings, "EMAIL_NOREPLY_FROM", settings.DEFAULT_FROM_EMAIL
            )
            try:
                send_mail(
                    subject="¡Tu visita fue registrada! Haz tu oferta ahora 🏠",
                    message=texto_email,
                    from_email=remitente_noreply,
                    recipient_list=[visita.usuario.email],
                    html_message=html_email,
                    fail_silently=False,
                )
            except Exception:
                # Fallback: si el remitente "noreply" no está verificado en el
                # proveedor (ej. Resend), reintenta con el remitente verificado.
                logger.warning(
                    f"Fallo envío con {remitente_noreply} para visita #{visita.id}; "
                    f"reintentando con {settings.DEFAULT_FROM_EMAIL}"
                )
                send_mail(
                    subject="¡Tu visita fue registrada! Haz tu oferta ahora 🏠",
                    message=texto_email,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[visita.usuario.email],
                    html_message=html_email,
                    fail_silently=False,
                )
            logger.info(
                f"Email de incentivo enviado a {visita.usuario.email} "
                f"tras marcar visita #{visita.id} como realizada"
            )
        except Exception as e:
            # El email no debe impedir la operación principal
            logger.error(
                f"Error enviando email de incentivo para visita #{visita.id}: {e}",
                exc_info=True,
            )

        messages.success(request, "Visita marcada como realizada. Se notificó al visitante por correo y Centro de Comunicaciones.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    return redirect("detalle_propiedad", prop_id=visita.propiedad.id)


# ================================================================
# GESTIÓN DE ARRIENDO
# ================================================================

@login_required
def gestionar_arriendo(request, visita_id):
    """Handler único para el flujo de arriendo."""
    visita = get_object_or_404(SolicitudVisita, id=visita_id)
    propiedad = visita.propiedad

    if propiedad.tipo_accion != "arriendo":
        messages.error(request, "Esta propiedad no es de tipo arriendo.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if request.method != "POST":
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    accion = request.POST.get("accion", "")
    es_usuario = request.user == visita.usuario
    es_corredor = request.user == visita.corredor
    es_admin = request.user.rol in ("gerente", "superadmin")
    es_dueno = request.user == propiedad.dueno
    puede_gestionar = es_corredor or es_admin or es_dueno

    if accion == "indicar_intencion":
        if not es_usuario:
            messages.error(request, "Solo el solicitante puede indicar intención de arriendo.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.estado != "realizada":
            messages.error(request, "La visita debe estar marcada como realizada primero.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.intencion_arriendo:
            messages.warning(request, "Ya manifestaste tu intención de arriendo.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        visita.intencion_arriendo = True
        visita.intencion_arriendo_at = timezone.now()
        visita.save()

        _notificar(
            recipient=visita.corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="Intención de arriendo manifestada",
            message=f"{request.user.get_full_name() or request.user.email} ha manifestado su intención de arrendar {propiedad.display_name_public()}.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        messages.success(request, "✅ Intención de arriendo registrada.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if accion == "subir_contrato":
        if not puede_gestionar:
            messages.error(request, "No tienes permiso.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if not visita.intencion_arriendo:
            messages.error(request, "El usuario aún no ha manifestado intención de arriendo.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.caso_cerrado:
            messages.error(request, "El caso ya está cerrado.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        contrato = request.FILES.get("contrato_arriendo")
        if not contrato:
            messages.error(request, "Debes seleccionar un archivo PDF.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        visita.contrato_arriendo = contrato
        visita.contrato_arriendo_subido_por = request.user
        visita.contrato_arriendo_ronda += 1
        visita.contrato_aceptado_arrendador = False
        visita.contrato_aceptado_arrendador_at = None
        visita.contrato_aceptado_arrendatario = False
        visita.contrato_aceptado_arrendatario_at = None
        visita.contrato_aceptado_at = None
        visita.save()

        _notificar(
            recipient=visita.usuario,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
            title="Contrato de arriendo listo",
            message=f"El contrato de arriendo para {propiedad.display_name_public()} está listo. Revísalo y acepta las condiciones.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )
        _notificar(
            recipient=propiedad.dueno,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
            title="Contrato de arriendo listo",
            message=f"El contrato de arriendo para tu propiedad {propiedad.display_name_public()} está listo. Revísalo y acepta las condiciones.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        messages.success(request, "📄 Contrato de arriendo subido. Ambas partes deben aceptarlo.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if accion == "contrato_aceptar":
        # Una parte (arrendador o arrendatario) acepta el contrato
        es_arrendador = request.user == propiedad.dueno
        es_arrendatario = request.user == visita.usuario
        if not (es_arrendador or es_arrendatario):
            messages.error(request, "Solo el arrendador o arrendatario puede aceptar el contrato.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if not visita.contrato_arriendo:
            messages.error(request, "El corredor aún no ha subido el contrato.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.caso_cerrado:
            messages.error(request, "El caso ya está cerrado.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        ahora = timezone.now()
        if es_arrendador and not visita.contrato_aceptado_arrendador:
            visita.contrato_aceptado_arrendador = True
            visita.contrato_aceptado_arrendador_at = ahora
        elif es_arrendatario and not visita.contrato_aceptado_arrendatario:
            visita.contrato_aceptado_arrendatario = True
            visita.contrato_aceptado_arrendatario_at = ahora
        else:
            messages.warning(request, "Ya aceptaste el contrato.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        # Verificar si ambas partes aceptaron
        if visita.contrato_aceptado_arrendador and visita.contrato_aceptado_arrendatario:
            visita.contrato_aceptado_at = ahora

            _notificar(
                recipient=visita.corredor,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="✅ Contrato de arriendo aceptado por ambas partes",
                message=f"Ambas partes aceptaron el contrato de arriendo para {propiedad.display_name_public()}. Ahora puedes proponer la cita notarial.",
                property_id=propiedad.id,
                related_object_id=visita.id,
            )
            messages.success(request, "✅ Contrato aceptado por ambas partes. Ahora el corredor debe proponer la cita notarial.")
        else:
            otra_parte = propiedad.dueno if es_arrendatario else visita.usuario
            _notificar(
                recipient=otra_parte,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="Contrato de arriendo aceptado",
                message=f"{request.user.get_full_name() or request.user.email} aceptó el contrato de arriendo para {propiedad.display_name_public()}. Te falta tu aceptación.",
                property_id=propiedad.id,
                related_object_id=visita.id,
            )
            messages.success(request, "✅ Contrato aceptado. Falta la aceptación de la otra parte.")

        visita.save()
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if accion == "contrato_objetar":
        # Una parte objeta el contrato con una razón
        es_arrendador = request.user == propiedad.dueno
        es_arrendatario = request.user == visita.usuario
        if not (es_arrendador or es_arrendatario):
            messages.error(request, "Solo el arrendador o arrendatario puede objetar el contrato.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if not visita.contrato_arriendo:
            messages.error(request, "No hay contrato que objetar.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.caso_cerrado:
            messages.error(request, "El caso ya está cerrado.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        razon = request.POST.get("razon", "").strip()
        if not razon:
            messages.error(request, "Debes escribir la razón de la objeción.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        # Resetear aceptaciones de ambas partes
        visita.contrato_aceptado_arrendador = False
        visita.contrato_aceptado_arrendador_at = None
        visita.contrato_aceptado_arrendatario = False
        visita.contrato_aceptado_arrendatario_at = None
        visita.contrato_aceptado_at = None
        visita.save()

        _notificar(
            recipient=visita.corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="❌ Contrato de arriendo objetado",
            message=f"{request.user.get_full_name() or request.user.email} ha OBJETADO el contrato de arriendo para {propiedad.display_name_public()}. Razón: {razon[:200]}. Debes subir una nueva versión (ronda {visita.contrato_arriendo_ronda + 1}).",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        # Notificar a la otra parte
        otra_parte = propiedad.dueno if es_arrendatario else visita.usuario
        _notificar(
            recipient=otra_parte,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="❌ Contrato objetado",
            message=f"{request.user.get_full_name() or request.user.email} ha objetado el contrato de arriendo. El corredor deberá subir una nueva versión.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        messages.warning(request, f"❌ Contrato objetado. El corredor subirá una nueva versión.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if accion == "notaria_proponer":
        if not puede_gestionar:
            messages.error(request, "No tienes permiso.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        notaria_nombre = request.POST.get("notaria_nombre", "").strip()
        notaria_direccion = request.POST.get("notaria_direccion", "").strip()
        notaria_fecha = request.POST.get("notaria_fecha", "").strip()
        notaria_hora = request.POST.get("notaria_hora", "").strip()

        if not (notaria_nombre and notaria_direccion and notaria_fecha and notaria_hora):
            messages.error(request, "Debes completar todos los campos de la notaría.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        from datetime import datetime as dt
        visita.notaria_nombre = notaria_nombre
        visita.notaria_direccion = notaria_direccion
        visita.notaria_fecha = dt.strptime(notaria_fecha, "%Y-%m-%d").date()
        visita.notaria_hora = dt.strptime(notaria_hora, "%H:%M").time()
        visita.notaria_confirmada = False
        visita.save()

        _notificar(
            recipient=visita.usuario,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
            title="Cita notarial propuesta",
            message=f"Se ha propuesto una cita notarial para {propiedad.display_name_public()}: {notaria_nombre}, {notaria_direccion}, el {notaria_fecha} a las {notaria_hora}.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        # Al proponer/actualizar notaría, resetear aceptaciones
        visita.notaria_aceptada_arrendador = False
        visita.notaria_aceptada_arrendador_at = None
        visita.notaria_aceptada_arrendatario = False
        visita.notaria_aceptada_arrendatario_at = None
        visita.save()

        # Notificar a ambas partes
        for noti_user in [visita.usuario, propiedad.dueno]:
            if noti_user != request.user:
                _notificar(
                    recipient=noti_user,
                    emitter=request.user,
                    source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
                    title="Cita notarial propuesta",
                    message=f"Se ha propuesto una cita notarial para {propiedad.display_name_public()}: {notaria_nombre}, {notaria_direccion}, el {notaria_fecha} a las {notaria_hora}.",
                    property_id=propiedad.id,
                    related_object_id=visita.id,
                )

        messages.success(request, "📅 Datos de notaría guardados.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if accion == "notaria_aceptar":
        es_arrendador = request.user == propiedad.dueno
        es_arrendatario = request.user == visita.usuario
        if not (es_arrendador or es_arrendatario):
            messages.error(request, "Solo el arrendador o arrendatario puede aceptar la cita notarial.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if not visita.notaria_nombre:
            messages.error(request, "El corredor aún no ha propuesto una cita notarial.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.caso_cerrado:
            messages.error(request, "El caso ya está cerrado.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        ahora = timezone.now()
        if es_arrendador and not visita.notaria_aceptada_arrendador:
            visita.notaria_aceptada_arrendador = True
            visita.notaria_aceptada_arrendador_at = ahora
        elif es_arrendatario and not visita.notaria_aceptada_arrendatario:
            visita.notaria_aceptada_arrendatario = True
            visita.notaria_aceptada_arrendatario_at = ahora
        else:
            messages.warning(request, "Ya aceptaste la cita notarial.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        # Si ambas partes aceptaron → notaria_confirmada = True automáticamente
        if visita.notaria_aceptada_arrendador and visita.notaria_aceptada_arrendatario:
            visita.notaria_confirmada = True
            visita.notaria_confirmada_at = ahora
            _notificar(
                recipient=visita.corredor,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="✅ Cita notarial aceptada por ambas partes",
                message=f"Ambas partes aceptaron la cita notarial para {propiedad.display_name_public()}. Puedes cerrar el caso cuando corresponda.",
                property_id=propiedad.id,
                related_object_id=visita.id,
            )
            messages.success(request, "✅ Cita notarial aceptada por ambas partes. El corredor puede cerrar el caso.")
        else:
            otra_parte = propiedad.dueno if es_arrendatario else visita.usuario
            _notificar(
                recipient=otra_parte,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="Cita notarial aceptada",
                message=f"{request.user.get_full_name() or request.user.email} aceptó la cita notarial para {propiedad.display_name_public()}. Te falta tu aceptación.",
                property_id=propiedad.id,
                related_object_id=visita.id,
            )
            messages.success(request, "✅ Cita notarial aceptada. Falta la aceptación de la otra parte.")

        visita.save()
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if accion == "notaria_objetar":
        es_arrendador = request.user == propiedad.dueno
        es_arrendatario = request.user == visita.usuario
        if not (es_arrendador or es_arrendatario):
            messages.error(request, "Solo el arrendador o arrendatario puede objetar la cita notarial.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if not visita.notaria_nombre:
            messages.error(request, "No hay cita notarial que objetar.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.caso_cerrado:
            messages.error(request, "El caso ya está cerrado.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        razon = request.POST.get("razon", "").strip()
        if not razon:
            messages.error(request, "Debes escribir la razón de la objeción.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        # Resetear aceptaciones
        visita.notaria_aceptada_arrendador = False
        visita.notaria_aceptada_arrendador_at = None
        visita.notaria_aceptada_arrendatario = False
        visita.notaria_aceptada_arrendatario_at = None
        visita.notaria_confirmada = False
        visita.notaria_confirmada_at = None
        visita.save()

        _notificar(
            recipient=visita.corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="❌ Cita notarial objetada",
            message=f"{request.user.get_full_name() or request.user.email} ha OBJETADO la cita notarial para {propiedad.display_name_public()}. Razón: {razon[:200]}. Debes proponer un nuevo horario.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        otra_parte = propiedad.dueno if es_arrendatario else visita.usuario
        _notificar(
            recipient=otra_parte,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="❌ Cita notarial objetada",
            message=f"{request.user.get_full_name() or request.user.email} ha objetado la cita notarial. El corredor deberá proponer un nuevo horario.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        messages.warning(request, f"❌ Cita notarial objetada. El corredor propondrá un nuevo horario.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if accion == "notaria_confirmar":
        if not es_usuario:
            messages.error(request, "Solo el solicitante puede confirmar la cita notarial.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if not visita.notaria_nombre:
            messages.error(request, "El corredor aún no ha propuesto una cita notarial.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.notaria_confirmada:
            messages.warning(request, "Ya confirmaste la cita notarial.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        visita.notaria_confirmada = True
        visita.notaria_confirmada_at = timezone.now()
        visita.save()

        _notificar(
            recipient=visita.corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title="Cita notarial confirmada",
            message=f"{request.user.get_full_name() or request.user.email} confirmó la cita notarial para {propiedad.display_name_public()} en {visita.notaria_nombre} el {visita.notaria_fecha.strftime('%d/%m/%Y')} a las {visita.notaria_hora.strftime('%H:%M')}.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        messages.success(request, "✅ Cita notarial confirmada.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if accion == "cerrar_caso":
        if not puede_gestionar:
            messages.error(request, "No tienes permiso para cerrar el caso.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if visita.caso_cerrado:
            messages.warning(request, "El caso ya está cerrado.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)
        if not visita.notaria_confirmada:
            messages.error(request, "La cita notarial debe estar confirmada.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        visita.caso_cerrado = True
        visita.caso_cerrado_at = timezone.now()
        visita.save()

        # Marcar la propiedad como arrendada retroactivamente desde la fecha de cierre
        propiedad.tipo_cierre = "arrendada"
        propiedad.fecha_cierre = visita.caso_cerrado_at
        propiedad.save(update_fields=["tipo_cierre", "fecha_cierre", "updated_at"])

        # Quitar destacada de la publicación (sigue visible en vitrina 30 días, pero no destaca)
        propiedad.publicaciones.filter(es_destacada=True, estado="publicada").update(
            es_destacada=False, renovacion_avisada=True
        )

        # ===== CREAR CIERRE ECONÓMICO AUTOMÁTICO =====
        try:
            # Usar canon rectificado desde contrato, o precio de propiedad como fallback
            precio_final = visita.canon_arriendo_final or propiedad.precio
            moneda_final = propiedad.tipo_moneda  # asumimos misma moneda
            _crear_cierre_automatico(
                propiedad=propiedad,
                corredor=visita.corredor,
                tipo_cierre="arriendo",
                precio=precio_final,
                moneda=moneda_final,
                tipo_comision_vendedor=visita.tipo_comision_arrendador,
                valor_comision_vendedor=visita.valor_comision_arrendador,
                tipo_comision_comprador=visita.tipo_comision_arrendatario,
                valor_comision_comprador=visita.valor_comision_arrendatario,
                fecha_cierre=visita.caso_cerrado_at,
            )
            logger.info(f"CierreEconomico creado automáticamente al cerrar caso arriendo #{visita.id}")
        except Exception as e:
            logger.error(f"Error creando CierreEconomico para arriendo #{visita.id}: {e}")

        _notificar(
            recipient=visita.usuario,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
            title="🎉 Caso de arriendo cerrado",
            message=f"El caso de arriendo para {propiedad.display_name_public()} ha sido cerrado exitosamente.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        _notificar(
            recipient=propiedad.dueno,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.GERENTE,
            title="🎉 Caso de arriendo cerrado",
            message=f"El caso de arriendo para tu propiedad {propiedad.display_name_public()} ha sido cerrado.",
            property_id=propiedad.id,
            related_object_id=visita.id,
        )

        messages.success(request, "🎉 Caso cerrado exitosamente.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    messages.error(request, f"Acción '{accion}' no reconocida.")
    return redirect("detalle_propiedad", prop_id=propiedad.id)


# ================================================================
# PROPUESTA DE COMPRA / ARRIENDO
# ================================================================

@login_required
def crear_propuesta(request, visita_id):
    """Usuario crea una propuesta de compra o arriendo."""
    visita = get_object_or_404(SolicitudVisita, id=visita_id)

    if request.user != visita.usuario:
        messages.error(request, "Solo el visitante puede hacer una propuesta.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if visita.estado != "realizada":
        messages.error(request, "La visita debe estar marcada como realizada.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    if hasattr(visita, "propuesta"):
        messages.warning(request, "Ya has creado una propuesta para esta visita.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    # Si el usuario está pausado, no puede crear propuesta
    if visita.pausado:
        messages.error(request, "Tu proceso está pausado porque otro comprador está en proceso de firma.")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    tipo_propuesta = "compra" if visita.propiedad.tipo_accion == "venta" else "arriendo"

    if request.method == "POST":
        monto = request.POST.get("monto_ofrecido", "").strip()
        if not monto:
            messages.error(request, "Debes indicar un monto.")
            return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

        moneda = request.POST.get("moneda", "PCL")
        condiciones = request.POST.get("condiciones", "").strip()

        nombre = request.POST.get("nombre_comprador", "").strip() or request.user.get_full_name() or request.user.username
        rut = request.POST.get("rut_comprador", "").strip() or (request.user.dni or "")
        email = request.POST.get("email_comprador", "").strip() or request.user.email
        telefono = request.POST.get("telefono_comprador", "").strip() or request.user.cel_phone

        propuesta = PropuestaCompra.objects.create(
            solicitud_visita=visita,
            tipo=tipo_propuesta,
            monto_ofrecido=monto,
            moneda=moneda,
            condiciones=condiciones,
            nombre_comprador=nombre,
            rut_comprador=rut,
            email_comprador=email,
            telefono_comprador=telefono,
            estado="pendiente",
        )

        # Si es propuesta de arriendo, marcar intencion_arriendo automaticamente
        if tipo_propuesta == "arriendo" and not visita.intencion_arriendo:
            visita.intencion_arriendo = True
            visita.intencion_arriendo_at = timezone.now()
            visita.save(update_fields=["intencion_arriendo", "intencion_arriendo_at", "updated_at"])

        _notificar(
            recipient=visita.corredor,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title=f"Nueva propuesta de {tipo_propuesta}",
            message=f"{nombre} ha hecho una propuesta de {tipo_propuesta} para {visita.propiedad.display_name_public()} por {moneda} ${float(monto):,.0f}.",
            property_id=visita.propiedad.id,
            related_object_id=propuesta.id,
        )

        _notificar(
            recipient=visita.propiedad.dueno,
            emitter=request.user,
            source_type=SourceTypeChoices.USUARIO_BASE,
            title=f"Propuesta de {tipo_propuesta} para tu propiedad",
            message=f"{nombre} ha hecho una propuesta de {tipo_propuesta} para tu propiedad {visita.propiedad.display_name_public()} por {moneda} ${float(monto):,.0f}.",
            property_id=visita.propiedad.id,
            related_object_id=propuesta.id,
        )

        messages.success(request, f"¡Propuesta de {tipo_propuesta} enviada!")
        return redirect("detalle_propiedad", prop_id=visita.propiedad.id)

    return redirect("detalle_propiedad", prop_id=visita.propiedad.id)


@login_required
def gestionar_propuesta(request, propuesta_id):
    """Gestionar propuesta: aceptar/rechazar/contraofertar."""
    propuesta = get_object_or_404(PropuestaCompra, id=propuesta_id)
    visita = propuesta.solicitud_visita
    propiedad = visita.propiedad

    es_corredor = request.user == visita.corredor
    es_admin = request.user.rol in ("gerente", "superadmin")
    es_dueno = request.user == propiedad.dueno

    if not (es_corredor or es_admin or es_dueno):
        messages.error(request, "No tienes permiso para gestionar esta propuesta.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if propuesta.estado != "pendiente":
        messages.error(request, f"La propuesta ya está {propuesta.get_estado_display()}.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "aceptar":
            # Solo el dueño puede aceptar definitivamente la propuesta
            if not es_dueno and not es_admin:
                messages.error(request, "Solo el propietario de la propiedad puede aceptar la propuesta.")
                return redirect("detalle_propiedad", prop_id=propiedad.id)

            propuesta.estado = "aceptada"
            propuesta.save()

            if propuesta.tipo == "compra":
                # FLUJO VENTA: crear ProcesoCompra (promesa → instrucciones → contrato → notaría → CBR)
                proceso = ProcesoCompra.objects.create(
                    propuesta=propuesta,
                    propiedad=propiedad,
                    comprador=visita.usuario,
                    vendedor=propiedad.dueno,
                    corredor=visita.corredor,
                    estado="propuesta_aceptada",
                )

                _notificar(
                    recipient=visita.usuario,
                    emitter=request.user,
                    source_type=SourceTypeChoices.USUARIO_BASE if es_dueno else SourceTypeChoices.GERENTE,
                    title=f"Propuesta de {propuesta.get_tipo_display()} aceptada",
                    message=f"¡Felicidades! Tu propuesta de {propuesta.get_tipo_display()} por {propuesta.moneda} ${float(propuesta.monto_ofrecido):,.0f} para {propiedad.display_name_public()} ha sido ACEPTADA por el dueño. El corredor preparará la Promesa de Compraventa.",
                    property_id=propiedad.id,
                    related_object_id=propuesta.id,
                )

                _notificar(
                    recipient=visita.corredor,
                    emitter=request.user,
                    source_type=SourceTypeChoices.USUARIO_BASE if es_dueno else SourceTypeChoices.GERENTE,
                    title="Propuesta aceptada - Iniciar proceso",
                    message=f"La propuesta de {visita.usuario.get_full_name() or visita.usuario.email} para {propiedad.display_name_public()} ha sido aceptada. Debes subir la Promesa de Compraventa para continuar.",
                    property_id=propiedad.id,
                    related_object_id=propuesta.id,
                )

                messages.success(request, "✅ Propuesta aceptada. El proceso de compra ha sido iniciado. El corredor debe subir la Promesa de Compraventa.")
            else:
                # FLUJO ARRIENDO: marcar intención, NO crear ProcesoCompra
                if not visita.intencion_arriendo:
                    visita.intencion_arriendo = True
                    visita.intencion_arriendo_at = timezone.now()
                    visita.save(update_fields=["intencion_arriendo", "intencion_arriendo_at", "updated_at"])

                _notificar(
                    recipient=visita.usuario,
                    emitter=request.user,
                    source_type=SourceTypeChoices.USUARIO_BASE if es_dueno else SourceTypeChoices.GERENTE,
                    title="✅ Propuesta de arriendo aceptada",
                    message=f"¡Felicidades! Tu propuesta de arriendo por {propuesta.moneda} ${float(propuesta.monto_ofrecido):,.0f} para {propiedad.display_name_public()} ha sido ACEPTADA por el dueño. El corredor preparará el Contrato de Arriendo.",
                    property_id=propiedad.id,
                    related_object_id=propuesta.id,
                )

                _notificar(
                    recipient=visita.corredor,
                    emitter=request.user,
                    source_type=SourceTypeChoices.USUARIO_BASE if es_dueno else SourceTypeChoices.GERENTE,
                    title="✅ Propuesta de arriendo aceptada - Subir Contrato",
                    message=f"La propuesta de arriendo de {visita.usuario.get_full_name() or visita.usuario.email} para {propiedad.display_name_public()} ha sido aceptada. Debes subir el Contrato de Arriendo para continuar.",
                    property_id=propiedad.id,
                    related_object_id=propuesta.id,
                )

                messages.success(request, "✅ Propuesta de arriendo aceptada. El corredor debe subir el Contrato de Arriendo.")

            return redirect("detalle_propiedad", prop_id=propiedad.id)

        elif accion == "rechazar":
            razon = request.POST.get("razon", "").strip()
            if not razon:
                messages.error(request, "Debes indicar una razón.")
                return redirect("detalle_propiedad", prop_id=propiedad.id)

            propuesta.estado = "rechazada"
            propuesta.save()

            _notificar(
                recipient=visita.usuario,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.USUARIO_BASE if es_dueno else SourceTypeChoices.GERENTE,
                title=f"Propuesta de {propuesta.get_tipo_display()} rechazada",
                message=f"Tu propuesta para {propiedad.display_name_public()} no ha sido aceptada. Razón: {razon}",
                property_id=propiedad.id,
                related_object_id=propuesta.id,
            )

            messages.warning(request, "Propuesta rechazada.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

        elif accion == "contraofertar":
            monto = request.POST.get("monto_contraoferta", "").strip()
            if not monto:
                messages.error(request, "Debes indicar un monto.")
                return redirect("detalle_propiedad", prop_id=propiedad.id)

            mensaje_contra = request.POST.get("mensaje_contraoferta", "").strip()

            propuesta.estado = "contra_oferta"
            propuesta.monto_ofrecido = monto
            propuesta.save()

            _notificar(
                recipient=visita.usuario,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.USUARIO_BASE if es_dueno else SourceTypeChoices.GERENTE,
                title="Contraoferta recibida",
                message=f"Han hecho una contraoferta de {propuesta.moneda} ${float(propuesta.monto_ofrecido):,.0f} para {propiedad.display_name_public()}. {mensaje_contra[:200]}",
                property_id=propiedad.id,
                related_object_id=propuesta.id,
            )

            messages.success(request, "Contraoferta enviada.")
            return redirect("detalle_propiedad", prop_id=propiedad.id)

    return redirect("detalle_propiedad", prop_id=propiedad.id)


# ================================================================
# PROCESO DE COMPRA-VENTA (FLUJO DOCUMENTAL)
# ================================================================

@login_required
def detalle_proceso_compra(request, proceso_id):
    """Ver detalle completo de un proceso de compra."""
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)

    if not _puede_ver_proceso(request, proceso):
        messages.error(request, "No tienes permiso para ver este proceso.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    observaciones = proceso.observaciones.all().select_related("autor").order_by("etapa", "ronda", "created_at")

    return render(request, "detalle_proceso_compra.html", {
        "proceso": proceso,
        "observaciones": observaciones,
    })


@login_required
def subir_promesa_compraventa(request, proceso_id):
    """
    Corredor sube el documento de Promesa de Compraventa.
    Inicia ronda de observaciones 1.
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)

    if not _puede_gestionar_proceso(request, proceso):
        messages.error(request, "Solo el corredor o administrador puede subir la Promesa.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if proceso.estado not in ("propuesta_aceptada", "promesa_observacion"):
        messages.error(request, f"No puedes subir Promesa en estado {proceso.get_estado_display()}.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if request.method == "POST":
        pdf = request.FILES.get("documento")
        if not pdf:
            messages.error(request, "Debes seleccionar un archivo PDF.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        proceso.promesa_documento = pdf
        proceso.promesa_subido_por = request.user
        proceso.promesa_ronda += 1
        proceso.promesa_aceptado_vendedor = False
        proceso.promesa_aceptado_comprador = False
        proceso.estado = "promesa_observacion"
        proceso.save()

        # Notificar a ambas partes
        _notificar(
            recipient=proceso.comprador,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="📄 Promesa de Compraventa lista para revisar",
            message=f"El corredor ha subido la Promesa de Compraventa para {proceso.propiedad.display_name_public()}. Revísala y haz observaciones o acéptala.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )
        _notificar(
            recipient=proceso.vendedor,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="📄 Promesa de Compraventa lista para revisar",
            message=f"El corredor ha subido la Promesa de Compraventa para tu propiedad {proceso.propiedad.display_name_public()}. Revísala y haz observaciones o acéptala.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )

        messages.success(request, "📄 Promesa de Compraventa subida. Ambas partes deben revisar y aceptar.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)


@login_required
def agregar_observacion_proceso(request, proceso_id, etapa):
    """
    Agregar observación a una etapa del proceso (promesa/instrucciones/contrato).
    El corredor puede adjuntar PDF en cada ocasión.
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)

    es_comprador = request.user == proceso.comprador
    es_vendedor = request.user == proceso.vendedor
    es_corredor = request.user == proceso.corredor
    es_admin = request.user.rol in ("gerente", "superadmin")
    es_parte = es_comprador or es_vendedor

    if not (es_parte or es_corredor or es_admin):
        messages.error(request, "No tienes permiso.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    # Validar etapa permitida según estado del proceso
    etapas_permitidas = {
        "promesa": ("propuesta_aceptada", "promesa_observacion"),
        "instrucciones": ("promesa_aceptada", "instrucciones_observacion"),
        "contrato": ("instrucciones_aceptada", "contrato_pendiente"),
    }

    if etapa not in etapas_permitidas:
        messages.error(request, "Etapa inválida.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if proceso.estado not in etapas_permitidas[etapa]:
        messages.error(request, f"No puedes hacer observaciones en esta etapa ({proceso.get_estado_display()}).")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    # Obtener ronda actual
    ronda_actual = getattr(proceso, f"{etapa}_ronda", 1)

    if request.method == "POST":
        texto = request.POST.get("texto", "").strip()
        archivo = request.FILES.get("archivo")

        if not texto and not archivo and not es_corredor:
            messages.error(request, "Debes escribir una observación.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        # Crear observación
        ObservacionProceso.objects.create(
            proceso=proceso,
            etapa=etapa,
            ronda=ronda_actual,
            autor=request.user,
            texto=texto,
            archivo=archivo,
        )

        notificar_a = []
        if es_comprador:
            notificar_a = [proceso.vendedor, proceso.corredor]
        elif es_vendedor:
            notificar_a = [proceso.comprador, proceso.corredor]
        elif es_corredor or es_admin:
            notificar_a = [proceso.comprador, proceso.vendedor]

        for r in notificar_a:
            _notificar(
                recipient=r,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR if es_corredor else SourceTypeChoices.USUARIO_BASE,
                title=f"Nueva observación - {dict(ObservacionProceso.ETAPA_CHOICES).get(etapa, 'Documento')}",
                message=f"{request.user.get_full_name() or request.user.email} ha agregado una observación en ronda {ronda_actual}: {texto[:200]}",
                property_id=proceso.propiedad.id,
                related_object_id=proceso.id,
            )

        messages.success(request, "Observación agregada.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)


@login_required
def aceptar_documento_proceso(request, proceso_id, etapa):
    """
    Una parte (comprador o vendedor) acepta el documento de una etapa.
    Cuando ambas partes aceptan, avanza a la siguiente etapa.
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)
    es_comprador = request.user == proceso.comprador
    es_vendedor = request.user == proceso.vendedor

    if not (es_comprador or es_vendedor):
        messages.error(request, "Solo el comprador o vendedor puede aceptar documentos.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if request.method != "POST":
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    ahora = timezone.now()

    if etapa == "promesa":
        if proceso.estado not in ("propuesta_aceptada", "promesa_observacion"):
            messages.error(request, "No hay Promesa pendiente de aceptación.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        if not proceso.promesa_documento:
            messages.error(request, "El corredor aún no ha subido la Promesa.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        if es_comprador and not proceso.promesa_aceptado_comprador:
            proceso.promesa_aceptado_comprador = True
            proceso.promesa_aceptado_comprador_at = ahora
        elif es_vendedor and not proceso.promesa_aceptado_vendedor:
            proceso.promesa_aceptado_vendedor = True
            proceso.promesa_aceptado_vendedor_at = ahora
        else:
            messages.warning(request, "Ya aceptaste este documento.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        # Verificar si ambas partes aceptaron
        if proceso.promesa_aceptado_comprador and proceso.promesa_aceptado_vendedor:
            proceso.estado = "promesa_aceptada"
            proceso.promesa_aceptado_at = ahora
            # PAUSAR otros procesos de la misma propiedad
            proceso.pausar_otros_procesos()
            mensaje_avance = " Ambas partes aceptaron. Ahora el corredor debe subir las Instrucciones Notariales."

            _notificar(
                recipient=proceso.corredor,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="✅ Promesa de Compraventa aceptada por ambas partes",
                message=f"Ambas partes aceptaron la Promesa de Compraventa para {proceso.propiedad.display_name_public()}. Todos los demás procesos han sido pausados. Debes subir las Instrucciones Notariales.",
                property_id=proceso.propiedad.id,
                related_object_id=proceso.id,
            )
        else:
            mensaje_avance = " Una parte aceptó. Falta la aceptación de la otra parte."
            # Notificar a la otra parte
            otra_parte = proceso.vendedor if es_comprador else proceso.comprador
            _notificar(
                recipient=otra_parte,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title=f"Promesa aceptada por {'comprador' if es_comprador else 'vendedor'}",
                message=f"{request.user.get_full_name() or request.user.email} aceptó la Promesa de Compraventa para {proceso.propiedad.display_name_public()}. Te falta tu aceptación.",
                property_id=proceso.propiedad.id,
                related_object_id=proceso.id,
            )

        proceso.save()
        messages.success(request, f"✅ Documento aceptado.{mensaje_avance}")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    elif etapa == "instrucciones":
        if proceso.estado not in ("promesa_aceptada", "instrucciones_observacion"):
            messages.error(request, "No hay Instrucciones pendientes de aceptación.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        if not proceso.instrucciones_documento:
            messages.error(request, "El corredor aún no ha subido las Instrucciones Notariales.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        if es_comprador and not proceso.instrucciones_aceptado_comprador:
            proceso.instrucciones_aceptado_comprador = True
            proceso.instrucciones_aceptado_comprador_at = ahora
        elif es_vendedor and not proceso.instrucciones_aceptado_vendedor:
            proceso.instrucciones_aceptado_vendedor = True
            proceso.instrucciones_aceptado_vendedor_at = ahora
        else:
            messages.warning(request, "Ya aceptaste este documento.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        if proceso.instrucciones_aceptado_comprador and proceso.instrucciones_aceptado_vendedor:
            proceso.estado = "instrucciones_aceptada"
            proceso.instrucciones_aceptado_at = ahora
            mensaje_avance = " Ambas partes aceptaron. El corredor debe subir el Contrato de Compraventa."

            _notificar(
                recipient=proceso.corredor,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="✅ Instrucciones Notariales aceptadas",
                message=f"Ambas partes aceptaron las Instrucciones Notariales para {proceso.propiedad.display_name_public()}. Debes subir el Contrato de Compraventa y los datos de la notaría.",
                property_id=proceso.propiedad.id,
                related_object_id=proceso.id,
            )
        else:
            mensaje_avance = " Una parte aceptó. Falta la otra parte."
            otra_parte = proceso.vendedor if es_comprador else proceso.comprador
            _notificar(
                recipient=otra_parte,
                emitter=request.user,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="Instrucciones aceptadas",
                message=f"{request.user.get_full_name() or request.user.email} aceptó las Instrucciones Notariales.",
                property_id=proceso.propiedad.id,
                related_object_id=proceso.id,
            )

        proceso.save()
        messages.success(request, f"✅ Documento aceptado.{mensaje_avance}")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    messages.error(request, "Etapa inválida.")
    return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)


@login_required
def subir_instrucciones_notariales(request, proceso_id):
    """
    Corredor sube Instrucciones Notariales (Promesa ya aceptada).
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)

    if not _puede_gestionar_proceso(request, proceso):
        messages.error(request, "Solo el corredor puede subir las Instrucciones.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if proceso.estado not in ("promesa_aceptada", "instrucciones_observacion"):
        messages.error(request, f"No puedes subir Instrucciones en estado {proceso.get_estado_display()}.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if request.method == "POST":
        pdf = request.FILES.get("documento")
        if not pdf:
            messages.error(request, "Debes seleccionar un archivo PDF.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        proceso.instrucciones_documento = pdf
        proceso.instrucciones_subido_por = request.user
        proceso.instrucciones_ronda += 1
        proceso.instrucciones_aceptado_vendedor = False
        proceso.instrucciones_aceptado_comprador = False
        proceso.estado = "instrucciones_observacion"
        proceso.save()

        _notificar(
            recipient=proceso.comprador,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="📄 Instrucciones Notariales listas",
            message=f"Las Instrucciones Notariales para {proceso.propiedad.display_name_public()} están listas. Revísalas y acéptalas.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )
        _notificar(
            recipient=proceso.vendedor,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="📄 Instrucciones Notariales listas",
            message=f"Las Instrucciones Notariales para {proceso.propiedad.display_name_public()} están listas. Revísalas y acéptalas.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )

        messages.success(request, "📄 Instrucciones Notariales subidas. Ambas partes deben aceptar.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)


@login_required
def subir_contrato_notaria(request, proceso_id):
    """
    Corredor sube Contrato de Compraventa + datos de notaría
    (Instrucciones ya aceptadas).
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)

    if not _puede_gestionar_proceso(request, proceso):
        messages.error(request, "Solo el corredor puede subir el Contrato.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if proceso.estado not in ("instrucciones_aceptada", "contrato_pendiente"):
        messages.error(request, f"No puedes subir Contrato en estado {proceso.get_estado_display()}.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if request.method == "POST":
        contrato_pdf = request.FILES.get("contrato_documento")
        notaria_nombre = request.POST.get("notaria_nombre", "").strip()
        notaria_direccion = request.POST.get("notaria_direccion", "").strip()
        notaria_fecha = request.POST.get("notaria_fecha", "").strip()
        notaria_hora = request.POST.get("notaria_hora", "").strip()

        if not contrato_pdf:
            messages.error(request, "Debes seleccionar el Contrato de Compraventa (PDF).")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        if not (notaria_nombre and notaria_direccion and notaria_fecha and notaria_hora):
            messages.error(request, "Debes completar todos los datos de la notaría.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

        from datetime import datetime as dt

        proceso.contrato_documento = contrato_pdf
        proceso.contrato_subido_por = request.user
        proceso.notaria_nombre = notaria_nombre
        proceso.notaria_direccion = notaria_direccion
        proceso.notaria_fecha = dt.strptime(notaria_fecha, "%Y-%m-%d").date()
        proceso.notaria_hora = dt.strptime(notaria_hora, "%H:%M").time()
        proceso.estado = "contrato_listo"
        proceso.save()

        _notificar(
            recipient=proceso.comprador,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="📄 Contrato de Compraventa listo",
            message=f"El Contrato de Compraventa para {proceso.propiedad.display_name_public()} está listo. La firma notarial será en {notaria_nombre}, {notaria_direccion}, el {notaria_fecha} a las {notaria_hora}.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )
        _notificar(
            recipient=proceso.vendedor,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="📄 Contrato de Compraventa listo",
            message=f"El Contrato de Compraventa para tu propiedad {proceso.propiedad.display_name_public()} está listo. Firma en {notaria_nombre} el {notaria_fecha} a las {notaria_hora}.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )

        messages.success(request, "📄 Contrato subido y datos de notaría guardados. Las partes deben asistir a la firma notarial.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)


@login_required
def marcar_firma_notarial(request, proceso_id):
    """
    Corredor marca que la firma notarial del Contrato de Compraventa fue realizada.
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)

    if not _puede_gestionar_proceso(request, proceso):
        messages.error(request, "Solo el corredor puede confirmar la firma notarial.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if proceso.estado != "contrato_listo":
        messages.error(request, "El Contrato debe estar listo antes de marcar la firma.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if request.method == "POST":
        proceso.contrato_firmado = True
        proceso.contrato_firmado_at = timezone.now()
        proceso.estado = "firma_notarial"
        proceso.save()

        _notificar(
            recipient=proceso.comprador,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="✅ Firma notarial realizada",
            message=f"La firma notarial del Contrato de Compraventa para {proceso.propiedad.display_name_public()} se ha realizado exitosamente. Ahora se procederá a la inscripción en el Conservador de Bienes Raíces.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )
        _notificar(
            recipient=proceso.vendedor,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="✅ Firma notarial realizada",
            message=f"La firma notarial para tu propiedad {proceso.propiedad.display_name_public()} se ha realizado exitosamente. Ahora se procederá a la inscripción en CBR.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )

        messages.success(request, "✅ Firma notarial marcada. Ahora debes iniciar la inscripción en CBR.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)


@login_required
def iniciar_inscripcion_cbr(request, proceso_id):
    """
    Etapa 4:
    Paso 1: Boton unico "Ingresar al CBR" que desaparece.
    Paso 2: Subida de documentos uno por uno con nombre + boton "+" (JS dinamico).
    Paso 3: Boton "Notificar resultado y cerrar proceso" con selector de resultado.
    Si aprobada -> finalizado, si rechazada -> escritura_rechazada.
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)

    if not _puede_gestionar_proceso(request, proceso):
        messages.error(request, 'No tienes permiso para gestionar este proceso.')
        return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)

    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        if accion == 'iniciar':
            # Paso 1: Solo marcar que se ingreso al CBR, notificar a las partes
            proceso.escritura_ingresada_at = timezone.now()
            proceso.estado = 'escritura_cbr'
            proceso.save(update_fields=['escritura_ingresada_at', 'estado', 'updated_at'])

            _notificar(
                recipient=proceso.vendedor,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR,
                title='Inscripcion iniciada en CBR',
                message=f'La escritura de la propiedad {proceso.propiedad.display_name_public()} ha sido ingresada al Conservador de Bienes Raices.',
                property_id=proceso.propiedad_id,
            )
            _notificar(
                recipient=proceso.comprador,
                emitter=request.user,
                source_type=SourceTypeChoices.CORREDOR,
                title='Inscripcion iniciada en CBR',
                message=f'La escritura de la propiedad {proceso.propiedad.display_name_public()} ha sido ingresada al Conservador de Bienes Raices.',
                property_id=proceso.propiedad_id,
            )

            messages.success(request, 'Inscripcion en CBR registrada. Se notifico a ambas partes.')
            return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)

        elif accion in ('subir_doc', 'subir_doc_json'):
            # Accion AJAX: subir un solo documento con nombre
            nombre_doc = request.POST.get('nombre_doc', '').strip()
            archivo = request.FILES.get('archivo')
            if not nombre_doc or not archivo:
                if accion == 'subir_doc_json':
                    return JsonResponse({'success': False, 'error': 'Debes indicar nombre y seleccionar archivo.'})
                messages.error(request, 'Debes indicar nombre y seleccionar archivo.')
                return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)

            obs = ObservacionProceso.objects.create(
                proceso=proceso,
                autor=request.user,
                etapa='cierre',
                ronda=0,
                texto=nombre_doc,
                archivo=archivo,
            )

            if accion == 'subir_doc_json':
                return JsonResponse({
                    'success': True,
                    'id': obs.id,
                    'nombre': obs.texto,
                    'url': obs.archivo.url,
                    'creado': obs.created_at.strftime('%d/%m/%Y %H:%M'),
                })
            messages.success(request, f'✅ Documento "{nombre_doc}" subido correctamente.')
            return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)

        elif accion == 'cerrar':
            # Paso 3: Resultado + cierre definitivo (no requiere docs, ya se subieron antes)
            resultado = request.POST.get('resultado', '')
            if resultado not in ('aprobada', 'rechazada'):
                messages.error(request, 'Debes seleccionar un resultado valido.')
                return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)

            # Verificar que hay al menos un documento subido
            docs_subidos = ObservacionProceso.objects.filter(proceso=proceso, etapa='cierre', archivo__isnull=False)
            if not docs_subidos.exists():
                messages.error(request, 'Debes subir al menos un documento antes de cerrar el proceso.')
                return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)

            # ===== MARCAR LA PROPIEDAD COMO VENDIDA SI SE APROBÓ =====
            propiedad_obj = proceso.propiedad
            if resultado == 'aprobada':
                propiedad_obj.tipo_cierre = 'vendida'
                propiedad_obj.fecha_cierre = timezone.now()
                propiedad_obj.save(update_fields=['tipo_cierre', 'fecha_cierre', 'updated_at'])

                # Quitar destacada de la publicación (sigue visible en vitrina 30 días)
                propiedad_obj.publicaciones.filter(es_destacada=True, estado="publicada").update(
                    es_destacada=False, renovacion_avisada=True
                )

                # ===== CREAR CIERRE ECONÓMICO AUTOMÁTICO PARA VENTA =====
                try:
                    _crear_cierre_automatico(
                        propiedad=propiedad_obj,
                        corredor=proceso.corredor,
                        tipo_cierre="venta",
                        precio=proceso.precio_venta_final or propiedad_obj.precio,
                        moneda=proceso.tipo_moneda_final or propiedad_obj.tipo_moneda,
                        tipo_comision_vendedor=proceso.tipo_comision_vendedor,
                        valor_comision_vendedor=proceso.valor_comision_vendedor,
                        tipo_comision_comprador=proceso.tipo_comision_comprador,
                        valor_comision_comprador=proceso.valor_comision_comprador,
                        fecha_cierre=timezone.now(),
                    )
                    logger.info(f"CierreEconomico creado automaticamente al finalizar venta #{proceso.id}")
                except Exception as e:
                    logger.error(f"Error creando CierreEconomico para venta #{proceso.id}: {e}")

            proceso.escritura_resultado = resultado
            proceso.escritura_resultado_at = timezone.now()
            proceso.escritura_comunicado = True
            proceso.escritura_comunicado_at = timezone.now()
            proceso.completado_at = timezone.now()
            proceso.estado = 'finalizado' if resultado == 'aprobada' else 'escritura_rechazada'

            proceso.save(update_fields=[
                'escritura_resultado', 'estado', 'escritura_resultado_at',
                'escritura_comunicado', 'escritura_comunicado_at', 'completado_at', 'updated_at'
            ])

            if resultado == 'aprobada':
                _notificar(
                    recipient=proceso.vendedor,
                    emitter=request.user,
                    source_type=SourceTypeChoices.CORREDOR,
                    title='Proceso de compra completado!',
                    message=f'Felicitaciones! El proceso de compraventa de {proceso.propiedad.display_name_public()} ha sido completado exitosamente.',
                    property_id=proceso.propiedad_id,
                )
                _notificar(
                    recipient=proceso.comprador,
                    emitter=request.user,
                    source_type=SourceTypeChoices.CORREDOR,
                    title='Proceso de compra completado!',
                    message=f'Felicitaciones! El proceso de compraventa de {proceso.propiedad.display_name_public()} ha sido completado exitosamente. La propiedad ahora esta inscrita a tu nombre!',
                    property_id=proceso.propiedad_id,
                )
                gerentes = User.objects.filter(rol__in=["gerente", "superadmin"], is_active=True)
                for gerente in gerentes:
                    _notificar(
                        recipient=gerente,
                        emitter=request.user,
                        source_type=SourceTypeChoices.CORREDOR,
                        title='🏆 Sugerencia: Crear Caso de Éxito',
                        message=(
                            f'Se ha completado la venta de {proceso.propiedad.display_name_public()}. '
                            f'¿Te gustaría crear un Caso de Éxito para destacar este logro? '
                            f'Ingresa a Casos de Éxito y asocia la Propiedad #{proceso.propiedad.id}.'
                        ),
                        property_id=proceso.propiedad_id,
                        related_object_id=proceso.id,
                    )
                messages.success(request, 'Proceso de compra completado exitosamente.')
            else:
                _notificar(
                    recipient=proceso.vendedor,
                    emitter=request.user,
                    source_type=SourceTypeChoices.CORREDOR,
                    title='Inscripcion rechazada',
                    message=f'La inscripcion en CBR de {proceso.propiedad.display_name_public()} fue rechazada. Se requiere gestion adicional.',
                    property_id=proceso.propiedad_id,
                )
                _notificar(
                    recipient=proceso.comprador,
                    emitter=request.user,
                    source_type=SourceTypeChoices.CORREDOR,
                    title='Inscripcion rechazada',
                    message=f'La inscripcion en CBR de {proceso.propiedad.display_name_public()} fue rechazada. Se requiere gestion adicional.',
                    property_id=proceso.propiedad_id,
                )
                messages.warning(request, 'Inscripcion rechazada por el CBR.')

            return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)

        messages.error(request, 'Accion no valida.')
        return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)

    messages.error(request, 'Metodo no permitido.')
    return redirect('detalle_propiedad', prop_id=proceso.propiedad_id)


@login_required
def reactivar_competidores(request, proceso_id):
    """
    Corredor reactiva todos los procesos pausados cuando el comprador no cumple
    con la Promesa de Compraventa.
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)

    if not _puede_gestionar_proceso(request, proceso):
        messages.error(request, "Solo el corredor puede reactivar los procesos.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if not proceso.otros_pausados:
        messages.error(request, "No hay procesos pausados para reactivar.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if request.method == "POST":
        # Reactivar todas las visitas pausadas por este proceso
        proceso.reactivar_otros_procesos()

        # Marcar este proceso como cancelado
        proceso.estado = "cancelado"
        proceso.save()

        # Notificar a todos los afectados
        visitas_reactivadas = SolicitudVisita.objects.filter(
            propiedad=proceso.propiedad,
            pausado=False,  # Acaban de ser reactivadas
            estado__in=["pendiente", "aceptada", "reprogramada", "realizada"],
        )

        _notificar(
            recipient=proceso.comprador,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="❌ Proceso cancelado - No cumpliste",
            message=f"Tu proceso de compra para {proceso.propiedad.display_name_public()} ha sido cancelado por no cumplir con la Promesa de Compraventa. La propiedad vuelve a estar disponible para otros compradores.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )

        _notificar(
            recipient=proceso.vendedor,
            emitter=request.user,
            source_type=SourceTypeChoices.CORREDOR,
            title="🔄 Proceso cancelado - Reactivando competidores",
            message=f"El proceso con {proceso.comprador.get_full_name() or proceso.comprador.email} para tu propiedad {proceso.propiedad.display_name_public()} ha sido cancelado. Otros interesados han sido reactivados.",
            property_id=proceso.propiedad.id,
            related_object_id=proceso.id,
        )

        messages.success(request, "🔄 Procesos reactivados. El proceso actual ha sido cancelado. Todos los interesados pueden continuar.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)


# ================================================================
# OBJETAR DOCUMENTO EN PROCESO DE COMPRA
# ================================================================

@login_required
def objetar_documento_proceso(request, proceso_id, etapa):
    """
    Una parte (comprador o vendedor) objeta el documento actual de una etapa.
    - Crea una observacion con el motivo y archivo adjunto (opcional)
    - Resetea las aceptaciones de ambas partes
    - Notifica al corredor que debe subir una nueva versión (nueva ronda)
    """
    proceso = get_object_or_404(ProcesoCompra, id=proceso_id)
    es_comprador = request.user == proceso.comprador
    es_vendedor = request.user == proceso.vendedor

    if not (es_comprador or es_vendedor):
        messages.error(request, "Solo el comprador o vendedor puede objetar documentos.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if request.method != "POST":
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    texto = request.POST.get("texto", "").strip()
    if not texto:
        messages.error(request, "Debes escribir la razón de la objeción.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    archivo = request.FILES.get("archivo")

    # Obtener ronda actual
    ronda_actual = getattr(proceso, f"{etapa}_ronda", 1)

    # Validar etapa
    etapas_validas = {
        "promesa": ("propuesta_aceptada", "promesa_observacion"),
        "instrucciones": ("promesa_aceptada", "instrucciones_observacion"),
    }
    if etapa not in etapas_validas or proceso.estado not in etapas_validas[etapa]:
        messages.error(request, "No se puede objetar el documento en esta etapa.")
        return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    # Verificar que la parte no haya aceptado ya
    if etapa == "promesa":
        if es_comprador and proceso.promesa_aceptado_comprador:
            messages.error(request, "Ya aceptaste la Promesa. No puedes objetar.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)
        if es_vendedor and proceso.promesa_aceptado_vendedor:
            messages.error(request, "Ya aceptaste la Promesa. No puedes objetar.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    if etapa == "instrucciones":
        if es_comprador and proceso.instrucciones_aceptado_comprador:
            messages.error(request, "Ya aceptaste las Instrucciones. No puedes objetar.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)
        if es_vendedor and proceso.instrucciones_aceptado_vendedor:
            messages.error(request, "Ya aceptaste las Instrucciones. No puedes objetar.")
            return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)

    # Crear observación de objeción
    ObservacionProceso.objects.create(
        proceso=proceso,
        etapa=etapa,
        ronda=ronda_actual,
        autor=request.user,
        texto=texto,
        archivo=archivo,
    )

    # Resetear aceptaciones de ambas partes para forzar nueva ronda
    if etapa == "promesa":
        proceso.promesa_aceptado_vendedor = False
        proceso.promesa_aceptado_vendedor_at = None
        proceso.promesa_aceptado_comprador = False
        proceso.promesa_aceptado_comprador_at = None
        proceso.promesa_aceptado_at = None
    elif etapa == "instrucciones":
        proceso.instrucciones_aceptado_vendedor = False
        proceso.instrucciones_aceptado_vendedor_at = None
        proceso.instrucciones_aceptado_comprador = False
        proceso.instrucciones_aceptado_comprador_at = None
        proceso.instrucciones_aceptado_at = None

    proceso.save()

    # Notificar al corredor
    _notificar(
        recipient=proceso.corredor,
        emitter=request.user,
        source_type=SourceTypeChoices.USUARIO_BASE,
        title=f"❌ Documento objetado - {dict(ObservacionProceso.ETAPA_CHOICES).get(etapa, etapa)}",
        message=f"{request.user.get_full_name() or request.user.email} ha OBJETADO el documento de {dict(ObservacionProceso.ETAPA_CHOICES).get(etapa, etapa)}. Razón: {texto[:200]}. Debes subir una nueva versión (ronda {int(ronda_actual) + 1}).",
        property_id=proceso.propiedad.id,
        related_object_id=proceso.id,
    )

    # Notificar a la otra parte
    otra_parte = proceso.vendedor if es_comprador else proceso.comprador
    _notificar(
        recipient=otra_parte,
        emitter=request.user,
        source_type=SourceTypeChoices.USUARIO_BASE,
        title=f"❌ Objeción - {dict(ObservacionProceso.ETAPA_CHOICES).get(etapa, etapa)}",
        message=f"{request.user.get_full_name() or request.user.email} ha objetado el documento. El corredor deberá subir una nueva versión.",
        property_id=proceso.propiedad.id,
        related_object_id=proceso.id,
    )

    messages.warning(request, f"❌ Objeción registrada. El corredor subirá una nueva versión del documento.")
    return redirect("detalle_propiedad", prop_id=proceso.propiedad.id)


# ================================================================
# FAVORITAS
# ================================================================

@login_required
def toggle_favorita(request, prop_id):
    """Agrega o quita una propiedad de favoritos (toggle)."""
    propiedad = get_object_or_404(Propiedad, id=prop_id)
    fav, created = FavoritaProp.objects.get_or_create(
        usuario=request.user,
        propiedad=propiedad,
    )
    if not created:
        fav.delete()
        es_favorita = False
        msg = "Propiedad eliminada de favoritas ❤️"
    else:
        es_favorita = True
        msg = "Propiedad agregada a favoritas ❤️"

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({"es_favorita": es_favorita, "msg": msg})

    messages.success(request, msg)
    ref = request.META.get('HTTP_REFERER')
    if ref:
        return redirect(ref)
    return redirect("detalle_propiedad", prop_id=prop.id)

# ===== STUBS for missing view functions =====

@login_required
def subir_orden_visita_firmada(request, *args, **kwargs):
    messages.error(request, "Funcionalidad en mantenimiento.")
    return redirect("home")


@login_required
def avanzar_a_instrucciones(request, *args, **kwargs):
    messages.error(request, "Funcionalidad en mantenimiento.")
    return redirect("home")


@login_required
def declarar_ronda_no_superada(request, *args, **kwargs):
    messages.error(request, "Funcionalidad en mantenimiento.")
    return redirect("home")


@login_required
def generar_afiche(request, prop_id=None, *args, **kwargs):
    """
    Genera el Afiche PDF (A4) con QR hacia el detalle de la propiedad
    para imprimir y colocar en el inmueble (transedntes escanean y llegan
    al detalle en la plataforma).
    """
    from .poster_utils import generate_poster

    if prop_id is None:
        prop_id = kwargs.get("prop_id")
    propiedad = get_object_or_404(Propiedad, id=prop_id)

    sitio = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
    url = f"https://{sitio}/prop/detalle/{propiedad.id}/"

    try:
        pdf_bytes = generate_poster(url)
    except Exception as e:
        logger.error(f"Error generando afiche PDF propiedad #{propiedad.id}: {e}", exc_info=True)
        messages.error(request, "No se pudo generar el afiche PDF. Intenta nuevamente.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="afiche-{propiedad.id}.pdf"'
    return response


@login_required
def generar_story_instagram(request, prop_id=None, *args, **kwargs):
    """
    Genera la historia de Instagram (PNG 1080x1920) con las imágenes y
    características de la propiedad para facilitar su publicación en IG.
    """
    from .market_utils import generate_instagram_story

    if prop_id is None:
        prop_id = kwargs.get("prop_id")
    propiedad = get_object_or_404(Propiedad, id=prop_id)

    sitio = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
    url = f"https://{sitio}/prop/detalle/{propiedad.id}/"

    try:
        png_bytes = generate_instagram_story(propiedad, url)
    except Exception as e:
        logger.error(f"Error generando story IG propiedad #{propiedad.id}: {e}", exc_info=True)
        messages.error(request, "No se pudo generar la historia de Instagram. Intenta nuevamente.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="story-ig-{propiedad.id}.png"'
    return response


@login_required
def generar_afiche_facebook(request, prop_id=None, *args, **kwargs):
    """
    Genera el afiche para Facebook Marketplace (PNG 1080x1350) con las
    imágenes y características de la propiedad, listo para subir al Market.
    """
    from .market_utils import generate_facebook_poster

    if prop_id is None:
        prop_id = kwargs.get("prop_id")
    propiedad = get_object_or_404(Propiedad, id=prop_id)

    sitio = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
    url = f"https://{sitio}/prop/detalle/{propiedad.id}/"

    try:
        png_bytes = generate_facebook_poster(propiedad, url)
    except Exception as e:
        logger.error(f"Error generando afiche FB propiedad #{propiedad.id}: {e}", exc_info=True)
        messages.error(request, "No se pudo generar el afiche de Facebook. Intenta nuevamente.")
        return redirect("detalle_propiedad", prop_id=propiedad.id)

    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="fb-market-{propiedad.id}.png"'
    return response
