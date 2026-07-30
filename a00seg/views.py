from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.http import HttpResponse
from a01Com.models import Communication, SourceTypeChoices
from .models import *
from .email_utils import send_confirmation_email, email_token_generator
from a03Prop.models import Propiedad, PublicacionProp, FotosPropiedad, ServiciosProp, ConfiguracionPagoPubli, CierreEconomico



def home(request):
    """Home del sitio con vitrina de propiedades, aside de destacadas y publicidad."""
    treinta_dias_atras = timezone.now() - timezone.timedelta(days=30)

    destacadas = PublicacionProp.objects.filter(
        estado="publicada", es_destacada=True, expira_at__gte=timezone.now()
    ).select_related("propiedad")[:5]

    # Vitrina: publicaciones activas vigentes + cerradas recientes (hasta 30 días)
    publicadas = PublicacionProp.objects.filter(
        estado="publicada"
    ).filter(
        Q(expira_at__gte=timezone.now()) |
        Q(propiedad__tipo_cierre__isnull=False, propiedad__fecha_cierre__gte=treinta_dias_atras)
    ).select_related("propiedad").order_by("-es_destacada", "-created_at")

    # Filtros
    tipo_accion = request.GET.get("tipo_accion")
    tipo_prop = request.GET.get("tipo_prop")
    comuna_id = request.GET.get("comuna")
    search = request.GET.get("q")

    if tipo_accion:
        publicadas = publicadas.filter(propiedad__tipo_accion=tipo_accion)
    if tipo_prop:
        publicadas = publicadas.filter(propiedad__tipo_prop=tipo_prop)
    if comuna_id:
        publicadas = publicadas.filter(propiedad__comuna_id=comuna_id)
    if search:
        publicadas = publicadas.filter(
            propiedad__calle__icontains=search
        ) | publicadas.filter(propiedad__descripcion_propiedad__icontains=search)

    # --- Filtro por rango de precios por moneda ---
    precio_moneda = request.GET.get("precio_moneda")
    precio_min = request.GET.get("precio_min")
    precio_max = request.GET.get("precio_max")
    if precio_moneda and (precio_min or precio_max):
        q_filter = Q(propiedad__tipo_moneda=precio_moneda)
        if precio_min:
            try:
                q_filter &= Q(propiedad__precio__gte=float(precio_min))
            except ValueError:
                pass
        if precio_max:
            try:
                q_filter &= Q(propiedad__precio__lte=float(precio_max))
            except ValueError:
                pass
        publicadas = publicadas.filter(q_filter)

    comunas = Comuna.objects.all().order_by("nombre")
    config_pago = ConfiguracionPagoPubli.objects.filter(activo=True).first()

    # IDs de propiedades favoritas del usuario autenticado
    favoritas_ids = set()
    if request.user.is_authenticated:
        from a03Prop.models import FavoritaProp
        favoritas_ids = set(
            FavoritaProp.objects.filter(usuario=request.user).values_list('propiedad_id', flat=True)
        )

    # --- Paginador ---
    page = request.GET.get("page", 1)
    paginator = Paginator(publicadas, 25)  # 25 por página = 5 filas de 5
    try:
        publicadas_page = paginator.page(page)
    except PageNotAnInteger:
        publicadas_page = paginator.page(1)
    except EmptyPage:
        publicadas_page = paginator.page(paginator.num_pages)

    return render(request, "home.html", {
        "destacadas": destacadas,
        "publicadas": publicadas_page,
        "comunas": comunas,
        "config_pago": config_pago,
        "current_filters": {
            "tipo_accion": tipo_accion,
            "tipo_prop": tipo_prop,
            "comuna": comuna_id,
            "q": search,
            "precio_moneda": precio_moneda,
            "precio_min": precio_min,
            "precio_max": precio_max,
        },
        "favoritas_ids": favoritas_ids,
        "paginator": paginator,
        "page_obj": publicadas_page,
    })


def nosotros_view(request):
    return render(request, "nosotros.html", {
        "funcionarios": Funcionario.objects.filter(is_active=True),
    })


def login_view(request):
    next_url = request.GET.get("next", "")
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        next_url = request.POST.get("next", "")
        # Buscar usuario por email
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None
        if user:
            login(request, user)
            messages.success(request, f"Bienvenido {user.get_full_name() or user.email}")
            if next_url:
                return redirect(next_url)
            return redirect("home")
        messages.error(request, "Email o contraseña incorrectos")
    return render(request, "login.html", {"next_url": next_url})


def logout_view(request):
    logout(request)
    return redirect("home")


def registro_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        password2 = request.POST.get("password2")
        dni = request.POST.get("dni")
        cel_phone = request.POST.get("cel_phone")
        first_name = request.POST.get("first_name", "")
        last_name = request.POST.get("last_name", "")

        if password != password2:
            messages.error(request, "Las contraseñas no coinciden")
            return render(request, "registro.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "El email ya está registrado")
            return render(request, "registro.html")

        # Autogenerar username desde el email
        username_base = email.split("@")[0].replace(".", "_").replace("-", "_")
        username = username_base
        contador = 1
        while User.objects.filter(username=username).exists():
            username = f"{username_base}_{contador}"
            contador += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            dni=dni,
            cel_phone=cel_phone,
            first_name=first_name,
            last_name=last_name,
            rol="base",
        )

        # Enviar correo de confirmación (con protección ante fallos)
        try:
            email_enviado = send_confirmation_email(user)
        except Exception:
            email_enviado = False

        if email_enviado:
            messages.success(
                request,
                "Registro exitoso. Te hemos enviado un correo de confirmación a "
                f"{email}. Revisa tu bandeja de entrada y también la carpeta de spam."
            )
        else:
            messages.success(
                request,
                "Registro exitoso. No pudimos enviar el correo de confirmación "
                "automáticamente, pero puedes solicitar uno nuevo desde tu perfil "
                "después de iniciar sesión."
            )
        return redirect("login")

    return render(request, "registro.html")


@login_required
def publica_view(request):
    """Redirige al nuevo flujo de solicitud de publicación."""
    from django.urls import reverse
    url = reverse("solicitar_publicacion")
    # Preservar parámetros GET (destacada, tipo_accion) si vienen desde planes.html
    qs = request.GET.urlencode()
    if qs:
        url += "?" + qs
    return redirect(url)


def planes_view(request):
    planes_corredor = PlanSuscripcion.objects.filter(tipo="corredor", activo=True)
    planes_vendedor = PlanSuscripcion.objects.filter(tipo="vendedor", activo=True)
    suscripcion = getattr(request.user, "suscripcion", None) if request.user.is_authenticated else None
    config_pago = ConfiguracionPagoPubli.objects.filter(activo=True).first()

    if request.method == "POST":
        plan_id = request.POST.get("plan_id")
        plan = get_object_or_404(PlanSuscripcion, id=plan_id, activo=True)
        fecha_fin = timezone.now() + timezone.timedelta(days=30 * plan.duracion_meses)

        if plan.tipo == "corredor":
            SuscripcionCorredor.objects.update_or_create(
                corredor=request.user,
                defaults={
                    "plan": plan,
                    "fecha_fin": fecha_fin,
                    "activa": True,
                },
            )
        else:
            SuscripcionVendedor.objects.update_or_create(
                vendedor=request.user,
                defaults={
                    "plan": plan,
                    "fecha_fin": fecha_fin,
                    "activa": True,
                },
            )
        messages.success(request, f"Plan {plan.nombre} contratado exitosamente.")
        return redirect("planes")

    return render(request, "planes.html", {
        "planes_corredor": planes_corredor,
        "planes_vendedor": planes_vendedor,
        "suscripcion": suscripcion,
        "config_pago": config_pago,
    })


@login_required
def perfil_view(request):
    if request.method == "POST":
        user = request.user
        first_name = request.POST.get("first_name", user.first_name)
        last_name = request.POST.get("last_name", user.last_name)
        user.first_name = first_name
        user.last_name = last_name
        # Sincronizar username con nombre completo
        nuevo_username = f"{first_name} {last_name}".strip()
        if nuevo_username and nuevo_username != user.username:
            if not User.objects.filter(username=nuevo_username).exclude(id=user.id).exists():
                user.username = nuevo_username
            # Si ya existe otro usuario con ese username, se deja el actual
        user.cel_phone = request.POST.get("cel_phone", user.cel_phone)
        user.domicilio = request.POST.get("domicilio", user.domicilio)
        user.curriculo = request.POST.get("curriculo", user.curriculo)
        user.comuna_id = request.POST.get("comuna") or user.comuna_id

        # DNI: validar unicidad manualmente antes de guardar
        dni_nuevo = request.POST.get("dni", "").strip()
        if dni_nuevo:
            if user.dni != dni_nuevo and User.objects.filter(dni=dni_nuevo).exclude(id=user.id).exists():
                messages.error(request, "El RUT/DNI ingresado ya está registrado por otro usuario.")
                return redirect("perfil")
            user.dni = dni_nuevo

        if request.FILES.get("foto"):
            user.foto = request.FILES["foto"]

        try:
            user.save()
            messages.success(request, "Perfil actualizado exitosamente.")
        except Exception:
            messages.error(request, "Ocurrió un error al guardar el perfil. Intenta nuevamente.")
        return redirect("perfil")

    regiones = Region.objects.all()
    comunas = Comuna.objects.all().order_by("region__nombre", "nombre")

    # Datos de suscripción para corredores
    suscripcion = None
    props_usadas = 0
    props_max = 0
    if request.user.rol == "corredor":
        suscripcion = getattr(request.user, "suscripcion", None)
        if suscripcion:
            props_max = suscripcion.plan.max_propiedades_simultaneas
            from a03Prop.models import CorredorProp
            props_usadas = CorredorProp.objects.filter(
                corredor=request.user,
                estado__in=["pendiente", "activa"]
            ).count()

    return render(request, "perfil.html", {
        "regiones": regiones,
        "comunas": comunas,
        "mis_propiedades": Propiedad.objects.filter(dueno=request.user),
        "comunicaciones": Communication.objects.filter(recipient=request.user, is_deleted=False)[:10],
        "suscripcion": suscripcion,
        "props_usadas": props_usadas,
        "props_max": props_max,
    })


@login_required
def gestion_view(request):
    """Panel de gestión - tabla unificada para todos los roles."""
    from a03Prop.models import SolicitudPublicacion, CorredorProp, ProcesoCompra, SolicitudVisita

    items = []
    props_con_item = set()
    comunicaciones = []
    corredores_pendientes = []
    publicaciones_pendientes = []
    solicitudes_pendientes = []
    mis_asignaciones = CorredorProp.objects.none()

    if request.user.rol in ("gerente", "superadmin"):
        # Todo el universo de propiedades
        publicaciones = PublicacionProp.objects.all().select_related('propiedad', 'publicante')
        solicitudes = SolicitudPublicacion.objects.all().select_related('propiedad', 'usuario', 'corredor_asignado')
        propiedades = Propiedad.objects.all()

        corredores_pendientes = User.objects.filter(rol="corredor", valido_por__isnull=True)
        publicaciones_pendientes = PublicacionProp.objects.filter(estado="en_revision")
        solicitudes_pendientes = SolicitudPublicacion.objects.filter(
            estado__in=["pago_revision", "pago_objetado", "datos_listos", "esperando_corredor"]
        )

        solicitudes_por_prop = {s.propiedad_id: s for s in solicitudes if s.propiedad_id}

        for pub in publicaciones:
            props_con_item.add(pub.propiedad_id)
            s = solicitudes_por_prop.get(pub.propiedad_id)
            cp = CorredorProp.objects.filter(propiedad=pub.propiedad, estado="activa").select_related('corredor').first()
            items.append(_make_item(pub.propiedad, s, pub, cp, pub.publicante, pub.es_destacada, pub.meses, 'publicacion'))

        for s in solicitudes:
            if s.propiedad_id and s.propiedad_id not in props_con_item:
                props_con_item.add(s.propiedad_id)
                cp = CorredorProp.objects.filter(propiedad=s.propiedad, estado="activa").select_related('corredor').first() if s.propiedad else None
                items.append(_make_item(s.propiedad, s, None, cp, s.usuario, s.es_destacada, s.meses, 'solicitud'))

        for p in propiedades:
            if p.id not in props_con_item:
                props_con_item.add(p.id)
                items.append(_make_item(p, None, None, None, p.dueno, False, 0, 'propiedad'))

    elif request.user.rol == "corredor":
        mis_asignaciones = CorredorProp.objects.filter(
            corredor=request.user, estado__in=["pendiente", "activa"]
        ).select_related('propiedad')
        props_asignadas = set(cp.propiedad_id for cp in mis_asignaciones)

        publicaciones_mias = PublicacionProp.objects.filter(publicante=request.user).select_related('propiedad')
        solicitudes_asignadas = SolicitudPublicacion.objects.filter(
            corredor_asignado=request.user
        ).select_related('propiedad', 'usuario')

        solicitudes_por_prop = {s.propiedad_id: s for s in solicitudes_asignadas if s.propiedad_id}

        for pub in publicaciones_mias:
            props_con_item.add(pub.propiedad_id)
            s = solicitudes_por_prop.get(pub.propiedad_id)
            cp = next((a for a in mis_asignaciones if a.propiedad_id == pub.propiedad_id), None)
            items.append(_make_item(pub.propiedad, s, pub, cp, pub.publicante, pub.es_destacada, pub.meses, 'publicacion'))

        for s in solicitudes_asignadas:
            if s.propiedad_id and s.propiedad_id not in props_con_item:
                props_con_item.add(s.propiedad_id)
                cp = next((a for a in mis_asignaciones if a.propiedad_id == s.propiedad_id), None)
                items.append(_make_item(s.propiedad, s, None, cp, s.usuario, s.es_destacada, s.meses, 'solicitud'))

        for cp in mis_asignaciones:
            if cp.propiedad_id not in props_con_item:
                props_con_item.add(cp.propiedad_id)
                items.append(_make_item(cp.propiedad, None, None, cp, cp.propiedad.dueno, False, 0, 'asignacion' if cp.estado != 'activa' else 'publicacion'))

    else:
        # Usuario base
        mis_propiedades = Propiedad.objects.filter(dueno=request.user)
        mis_publicaciones = PublicacionProp.objects.filter(publicante=request.user).select_related('propiedad')
        mis_solicitudes = SolicitudPublicacion.objects.filter(usuario=request.user).select_related('propiedad')
        comunicaciones = Communication.objects.filter(recipient=request.user, is_deleted=False)[:20]

        solicitudes_por_prop = {s.propiedad_id: s for s in mis_solicitudes if s.propiedad_id}

        for pub in mis_publicaciones:
            props_con_item.add(pub.propiedad_id)
            s = solicitudes_por_prop.get(pub.propiedad_id)
            items.append(_make_item(pub.propiedad, s, pub, None, None, pub.es_destacada, pub.meses, 'publicacion'))

        for s in mis_solicitudes:
            if s.propiedad_id and s.propiedad_id not in props_con_item:
                props_con_item.add(s.propiedad_id)
                items.append(_make_item(s.propiedad, s, None, None, None, s.es_destacada, s.meses, 'solicitud'))

        for p in mis_propiedades:
            if p.id not in props_con_item:
                items.append(_make_item(p, None, None, None, None, False, 0, 'propiedad'))

    # Enriquecer cada item con procesos y etapa de gestión
    for item in items:
        prop = item['propiedad']
        if prop:
            item['procesos'] = list(ProcesoCompra.objects.filter(
                propiedad=prop
            ).exclude(estado__in=["cancelado", "finalizado"]).select_related('comprador', 'vendedor', 'corredor'))
            item['etapa_gestion'] = _get_etapa_gestion(item)
            item['visitas_count'] = SolicitudVisita.objects.filter(propiedad=prop).count()
        else:
            item['procesos'] = []
            item['etapa_gestion'] = ""
            item['visitas_count'] = 0

    return render(request, "gestion_unificada.html", {
        "items": items,
        "rol": request.user.rol,
        "corredores_pendientes": corredores_pendientes,
        "publicaciones_pendientes": publicaciones_pendientes,
        "solicitudes_pendientes": solicitudes_pendientes,
        "mis_asignaciones": mis_asignaciones,
        "comunicaciones": comunicaciones,
    })


def _make_item(propiedad, solicitud, publicacion, corredor_prop, cliente, es_destacada, meses, tipo):
    return {
        'solicitud_id': solicitud.id if solicitud else None,
        'solicitud': solicitud,
        'publicacion': publicacion,
        'propiedad': propiedad,
        'es_destacada': es_destacada,
        'meses': meses,
        'tipo': tipo,
        'corredor_prop': corredor_prop,
        'cliente': cliente,
        'procesos': [],
        'etapa_gestion': "",
        'visitas_count': 0,
    }


def _get_etapa_gestion(item):
    prop = item.get('propiedad')
    if not prop:
        return ""
    if prop.tipo_cierre:
        return "✅ Cerrada"
    procesos = item.get('procesos', [])
    if procesos:
        p = procesos[0]
        etapas = {
            "propuesta_aceptada": "📄 Propuesta aceptada",
            "promesa_observacion": "📝 Promesa en revisión",
            "promesa_aceptada": "📝 Promesa aceptada",
            "instrucciones_observacion": "📋 Instrucciones en revisión",
            "instrucciones_aceptada": "📋 Instrucciones aceptadas",
            "contrato_pendiente": "📑 Pendiente contrato",
            "contrato_listo": "📑 Contrato listo",
            "firma_notarial": "✍️ Firma notarial",
            "escritura_cbr": "🏛️ En CBR",
            "escritura_aprobada": "✅ Escritura inscrita",
            "escritura_rechazada": "❌ Escritura rechazada",
        }
        return etapas.get(p.estado, f"🔄 {p.get_estado_display()}")
    solicitud = item.get('solicitud')
    if solicitud:
        if solicitud.estado == "publicada":
            return "✅ Publicada"
        elif solicitud.estado in ("pago_revision", "pago_objetado"):
            return "💳 Pago " + ("revisión" if solicitud.estado == "pago_revision" else "objetado")
        elif solicitud.estado == "pago_aprobado":
            return "💳 Pago aprobado"
        elif solicitud.estado == "en_revision_corredor":
            return "👤 Asignando corredor"
        elif solicitud.estado in ("og_pendiente",):
            return "📄 OG pendiente"
        elif solicitud.estado == "og_aceptada":
            return "📄 OG aceptada"
        elif solicitud.estado == "en_validacion":
            return "🔍 En validación"
        return f"📋 {solicitud.get_estado_display()}"
    publicacion = item.get('publicacion')
    if publicacion:
        if publicacion.estado == "publicada":
            return "📢 Publicada"
        elif publicacion.estado == "en_revision":
            return "⏳ En revisión"
        return f"📢 {publicacion.get_estado_display()}"
    if item.get('corredor_prop'):
        return "👤 Asignada a corredor"
    if prop.estado == "borrador":
        return "📝 Borrador"
    return prop.get_estado_display() if prop.estado else ""


@login_required
def agenda_view(request):
    if request.user.rol not in ("corredor", "gerente", "superadmin"):
        messages.error(request, "No tienes permisos para acceder a esta sección.")
        return redirect("home")

    # ── Navegación ─────────────────────────────────────────
    vista = request.GET.get("vista", "mes")  # mes / semana / dia
    hoy = timezone.localdate()

    try:
        anio = int(request.GET.get("anio", hoy.year))
    except ValueError:
        anio = hoy.year
    try:
        mes = int(request.GET.get("mes", hoy.month))
    except ValueError:
        mes = hoy.month
    # Clamp month
    if mes < 1:
        mes = 1
        anio -= 1
    elif mes > 12:
        mes = 12
        anio += 1

    try:
        dia = int(request.GET.get("dia", hoy.day))
    except ValueError:
        dia = hoy.day

    from datetime import date, timedelta, time
    import calendar

    # Manejar navegación nav=ant / nav=sig para semana y día
    nav = request.GET.get("nav", "")
    if nav == "ant":
        if vista == "semana":
            ref_antes = date(anio, mes, dia) - timedelta(days=7)
        else:
            ref_antes = date(anio, mes, dia) - timedelta(days=1)
        anio, mes, dia = ref_antes.year, ref_antes.month, ref_antes.day
    elif nav == "sig":
        if vista == "semana":
            ref_desp = date(anio, mes, dia) + timedelta(days=7)
        else:
            ref_desp = date(anio, mes, dia) + timedelta(days=1)
        anio, mes, dia = ref_desp.year, ref_desp.month, ref_desp.day

    # Fecha de referencia
    ref_date = date(anio, mes, dia)

    # ── Bloques del usuario ────────────────────────────────
    base_qs = AgendaCorredor.objects.filter(corredor=request.user, activo=True)

    # Delimitamos según la vista
    if vista == "mes":
        _, ultimo_dia = calendar.monthrange(anio, mes)
        desde = date(anio, mes, 1)
        hasta = date(anio, mes, ultimo_dia)
    elif vista == "semana":
        # Lunes de la semana que contiene ref_date
        lunes = ref_date - timedelta(days=ref_date.weekday())
        desde = lunes
        hasta = lunes + timedelta(days=6)
    else:  # dia
        desde = ref_date
        hasta = ref_date

    bloques = base_qs.filter(fecha__gte=desde, fecha__lte=hasta).order_by("fecha", "hora_inicio")

    # ── Acciones POST ──────────────────────────────────────
    accion = request.POST.get("accion", "")

    if accion == "crear_uno":
        # Crea un bloque de 1 hora
        fecha_str = request.POST.get("fecha", "")
        hora_str = request.POST.get("hora_inicio", "")
        if fecha_str and hora_str:
            try:
                h, m = hora_str.split(":")
                hora_obj = time(int(h), int(m))
                hora_fin = time(hora_obj.hour + 1, hora_obj.minute) if hora_obj.hour < 23 else time(23, 59)
                AgendaCorredor.objects.create(
                    corredor=request.user,
                    fecha=fecha_str,
                    hora_inicio=hora_obj,
                    hora_fin=hora_fin,
                    cupos_por_hora=1,
                )
                messages.success(request, f"Bloque creado: {fecha_str} {hora_str}–{hora_fin.strftime('%H:%M')}")
            except Exception:
                messages.error(request, "Formato de hora inválido.")
        else:
            messages.error(request, "Debes indicar fecha y hora de inicio.")
        return redirect(f"{request.path}?vista={vista}&anio={anio}&mes={mes}&dia={dia}")

    elif accion == "crear_masivo":
        # Crea N bloques consecutivos de 1 hora
        fecha_str = request.POST.get("fecha", "")
        hora_str = request.POST.get("hora_inicio", "")
        cantidad_str = request.POST.get("cantidad", "1")
        if fecha_str and hora_str:
            try:
                h, m = hora_str.split(":")
                hora_base = time(int(h), int(m))
                cantidad = int(cantidad_str)
                if cantidad < 1 or cantidad > 48:
                    messages.error(request, "La cantidad debe estar entre 1 y 48.")
                    return redirect(f"{request.path}?vista={vista}&anio={anio}&mes={mes}&dia={dia}")
                creados = 0
                for i in range(cantidad):
                    h_act = hora_base.hour + i
                    if h_act >= 24:
                        break
                    h_inicio = time(h_act, hora_base.minute)
                    h_fin = time(h_act + 1, hora_base.minute) if h_act < 23 else time(23, 59)
                    AgendaCorredor.objects.get_or_create(
                        corredor=request.user,
                        fecha=fecha_str,
                        hora_inicio=h_inicio,
                        defaults={
                            "hora_fin": h_fin,
                            "cupos_por_hora": 1,
                        }
                    )
                    creados += 1
                messages.success(request, f"{creados} bloque(s) creados desde las {hora_str}.")
            except Exception as e:
                messages.error(request, f"Error al crear bloques: {e}")
        else:
            messages.error(request, "Debes indicar fecha y hora de inicio.")
        return redirect(f"{request.path}?vista={vista}&anio={anio}&mes={mes}&dia={dia}")

    elif accion == "eliminar":
        bloque_id = request.POST.get("bloque_id", "")
        if bloque_id:
            bloque = get_object_or_404(AgendaCorredor, id=bloque_id, corredor=request.user)
            bloque.delete()
            messages.success(request, "Bloque eliminado.")
        return redirect(f"{request.path}?vista={vista}&anio={anio}&mes={mes}&dia={dia}")

    # ── Contexto para la plantilla ─────────────────────────
    from collections import defaultdict

    # Agrupar bloques por fecha (usar string YYYY-MM-DD como key para coincidir con template)
    bloques_por_fecha = defaultdict(list)
    for b in bloques:
        key = b.fecha.isoformat()  # "2026-06-20"
        bloques_por_fecha[key].append(b)

    # Días del mes para el calendario
    if vista == "mes":
        _, ultimo_dia = calendar.monthrange(anio, mes)
        mes_dias = [date(anio, mes, d) for d in range(1, ultimo_dia + 1)]
        # Días de relleno al inicio (lunes=0)
        primer_dia_semana = mes_dias[0].weekday()
        relleno_inicio = [None] * primer_dia_semana
        mes_calendario = relleno_inicio + mes_dias
    else:
        mes_calendario = []

    # Días de la semana para vista semanal
    if vista == "semana":
        dias_semana = [(desde + timedelta(days=i)) for i in range(7)]
    else:
        dias_semana = []

    # Horas del día para vista diaria / semanal
    horas_del_dia = [f"{h:02d}:00" for h in range(6, 23)]  # 06:00 a 22:00

    # Navegación
    mes_ant = mes - 1 if mes > 1 else 12
    anio_ant = anio if mes > 1 else anio - 1
    mes_sig = mes + 1 if mes < 12 else 1
    anio_sig = anio if mes < 12 else anio + 1

    return render(request, "agenda.html", {
        "vista": vista,
        "anio": anio,
        "mes": mes,
        "dia": dia,
        "hoy": hoy,
        "ref_date": ref_date,
        "desde": desde,
        "hasta": hasta,
        "bloques": bloques,
        "bloques_por_fecha": dict(bloques_por_fecha),
        "mes_calendario": mes_calendario,
        "dias_semana": dias_semana,
        "horas_del_dia": horas_del_dia,
        "mes_ant": mes_ant,
        "anio_ant": anio_ant,
        "mes_sig": mes_sig,
        "anio_sig": anio_sig,
    })


@login_required
def validar_corredores_view(request):
    if request.user.rol not in ("superadmin", "gerente"):
        messages.error(request, "No tienes permisos para validar corredores.")
        return redirect("home")

    if request.method == "POST":
        corredor_id = request.POST.get("corredor_id")
        accion = request.POST.get("accion")
        corredor = get_object_or_404(User, id=corredor_id, rol="corredor")

        if accion == "validar":
            corredor.valido_por = request.user
            corredor.save()
            Communication.objects.create(
                recipient=corredor,
                emitter_user=request.user,
                source_type=SourceTypeChoices.GERENTE,
                title="Cuenta validada",
                message="Tu cuenta de corredor ha sido validada. Ya puedes operar en la plataforma.",
            )
            messages.success(request, f"Corredor {corredor.get_full_name()} validado.")
        elif accion == "rechazar":
            corredor.is_active = False
            corredor.save()
            messages.warning(request, f"Corredor {corredor.get_full_name()} rechazado.")

        return redirect("validar_corredores")

    corredores_pendientes = User.objects.filter(rol="corredor", valido_por__isnull=True, is_active=True)
    return render(request, "validar_corredores.html", {
        "corredores_pendientes": corredores_pendientes,
    })


@login_required
def crear_gerente_view(request):
    if request.user.rol != "superadmin":
        messages.error(request, "Solo el Superadmin puede crear gerentes.")
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        first_name = request.POST.get("first_name", "")
        last_name = request.POST.get("last_name", "")
        dni = request.POST.get("dni")

        if User.objects.filter(username=username).exists():
            messages.error(request, "El username ya existe.")
            return render(request, "crear_gerente.html")

        gerente = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            dni=dni,
            rol="gerente",
            valido_por=request.user,
        )
        messages.success(request, f"Gerente {gerente.get_full_name()} creado exitosamente.")
        return redirect("crear_gerente")

    return render(request, "crear_gerente.html")


# ============================================================
# NUEVO: FLUJO DE POSTULACIÓN A CORREDOR
# ============================================================

def se_nuestro_agente(request):
    """Paso 1: Muestra los planes disponibles para corredores."""
    planes = PlanSuscripcion.objects.filter(tipo="corredor", activo=True)
    return render(request, "se_nuestro_agente.html", {"planes": planes})


@login_required
def postular_corredor(request, plan_id):
    """Paso 2: Formulario de postulación con los datos + comprobante."""
    plan = get_object_or_404(PlanSuscripcion, id=plan_id, tipo="corredor", activo=True)
    comunas = Comuna.objects.all().order_by("nombre")
    regiones = Region.objects.all()

    if request.method == "POST":
        nombres = request.POST.get("nombres", "").strip()
        apellidos = request.POST.get("apellidos", "").strip()
        email = request.POST.get("email", "").strip().lower()
        dni = request.POST.get("dni", "").strip()
        cel_phone = request.POST.get("cel_phone", "").strip()
        domicilio = request.POST.get("domicilio", "").strip()
        curriculo = request.POST.get("curriculo", "").strip()
        comuna_id = request.POST.get("comuna")
        comprobante = request.FILES.get("comprobante")
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        errores = []

        # Validar campos requeridos
        if not nombres:
            errores.append("El campo Nombres es obligatorio.")
        if not apellidos:
            errores.append("El campo Apellidos es obligatorio.")
        if not email:
            errores.append("El campo Email es obligatorio.")
        if not comprobante:
            errores.append("Debes subir el comprobante de depósito.")

        if not password:
            errores.append("La contraseña es obligatoria.")
        elif password != password2:
            errores.append("Las contraseñas no coinciden.")

        # Verificar email único
        if email and User.objects.filter(email=email).exclude(
            id=request.user.id if request.user.is_authenticated else None
        ).exists():
            errores.append("El email ya está registrado por otro usuario.")

        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, "postular_corredor.html", {
                "plan": plan,
                "comunas": comunas,
                "regiones": regiones,
                "datos": request.POST,
            })

        usuario = None
        # Si el usuario está autenticado y tiene cuenta, lo vinculamos
        if request.user.is_authenticated:
            usuario = request.user
            # Actualizar sus datos
            usuario.first_name = nombres
            usuario.last_name = apellidos
            usuario.dni = dni
            usuario.cel_phone = cel_phone
            usuario.domicilio = domicilio
            usuario.curriculo = curriculo
            if comuna_id:
                usuario.comuna_id = comuna_id
            usuario.save()
        else:
            # Verificar si ya existe usuario con ese email
            try:
                usuario = User.objects.get(email=email)
                # Si ya existe, actualizamos datos
                usuario.first_name = nombres
                usuario.last_name = apellidos
                usuario.dni = dni
                usuario.cel_phone = cel_phone
                usuario.domicilio = domicilio
                usuario.curriculo = curriculo
                if comuna_id:
                    usuario.comuna_id = comuna_id
                if password:
                    usuario.set_password(password)
                usuario.save()
            except User.DoesNotExist:
                # Crear usuario con rol base
                username_base = email.split("@")[0].replace(".", "_").replace("-", "_")
                username = username_base
                contador = 1
                while User.objects.filter(username=username).exists():
                    username = f"{username_base}_{contador}"
                    contador += 1

                usuario = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=nombres,
                    last_name=apellidos,
                    dni=dni,
                    cel_phone=cel_phone,
                    domicilio=domicilio,
                    curriculo=curriculo,
                    comuna_id=comuna_id or None,
                    rol="base",
                )

        # Crear la solicitud
        solicitud = SolicitudCorredor.objects.create(
            usuario=usuario,
            nombres=nombres,
            apellidos=apellidos,
            email=email,
            dni=dni,
            cel_phone=cel_phone,
            domicilio=domicilio,
            curriculo=curriculo,
            comuna_id=comuna_id or None,
            plan=plan,
            comprobante=comprobante,
            estado="pendiente",
        )

        # Notificar a superadmins y gerentes
        admins = User.objects.filter(
            rol__in=["superadmin", "gerente"], is_active=True
        )
        for admin in admins:
            Communication.objects.create(
                recipient=admin,
                emitter_user=usuario,
                source_type=SourceTypeChoices.USUARIO_BASE,
                title="Nueva postulación a corredor",
                message=(
                    f"El usuario {nombres} {apellidos} ({email}) ha postulado "
                    f"al plan {plan.nombre}. Revisa sus antecedentes en el panel de gestión."
                ),
                related_object_id=solicitud.id,
            )

        messages.success(
            request,
            "¡Postulación recibida! Hemos enviado tu solicitud a revisión. "
            "Te contactaremos por email y Centro de Comunicaciones cuando esté habilitada."
        )
        # Autenticar al usuario si se acaba de registrar
        if not request.user.is_authenticated:
            user_auth = authenticate(request, username=usuario.username, password=password)
            if user_auth:
                login(request, user_auth)
        return redirect("home")

    return render(request, "postular_corredor.html", {
        "plan": plan,
        "comunas": comunas,
        "regiones": regiones,
        "datos": {},
    })


@login_required
def revisar_postulaciones(request):
    """Vista para que superadmin/gerente vea y gestione postulaciones."""
    if request.user.rol not in ("superadmin", "gerente"):
        messages.error(request, "No tienes permisos para acceder a esta sección.")
        return redirect("home")

    filtro = request.GET.get("filtro", "pendientes")
    if filtro == "pendientes":
        postulaciones = SolicitudCorredor.objects.filter(estado__in=["pendiente", "en_dialogo"])
    elif filtro == "aprobadas":
        postulaciones = SolicitudCorredor.objects.filter(estado="aprobada")
    elif filtro == "rechazadas":
        postulaciones = SolicitudCorredor.objects.filter(estado="rechazada")
    else:
        postulaciones = SolicitudCorredor.objects.all()

    return render(request, "revisar_postulaciones.html", {
        "postulaciones": postulaciones,
        "filtro_actual": filtro,
    })


@login_required
def detalle_postulacion(request, solicitud_id):
    """Ver detalle de una postulación y aprobar/rechazar con observaciones."""
    if request.user.rol not in ("superadmin", "gerente"):
        messages.error(request, "No tienes permisos.")
        return redirect("home")

    solicitud = get_object_or_404(SolicitudCorredor, id=solicitud_id)

    if request.method == "POST":
        accion = request.POST.get("accion")  # aprobar, rechazar, en_dialogo
        observaciones = request.POST.get("observaciones", "").strip()

        if accion == "aprobar":
            usuario = solicitud.usuario
            if not usuario:
                # Crear usuario si no existe (por si acaso)
                username_base = solicitud.email.split("@")[0].replace(".", "_").replace("-", "_")
                username = username_base
                cont = 1
                while User.objects.filter(username=username).exists():
                    username = f"{username_base}_{cont}"
                    cont += 1
                from django.contrib.auth.hashers import make_password
                import secrets
                temp_pass = secrets.token_urlsafe(10)
                usuario = User.objects.create_user(
                    username=username,
                    email=solicitud.email,
                    password=temp_pass,
                    first_name=solicitud.nombres,
                    last_name=solicitud.apellidos,
                    dni=solicitud.dni,
                    cel_phone=solicitud.cel_phone,
                    domicilio=solicitud.domicilio,
                    curriculo=solicitud.curriculo,
                    comuna=solicitud.comuna,
                    rol="corredor",
                    valido_por=request.user,
                )
                solicitud.usuario = usuario
            else:
                # Cambiar rol a corredor
                usuario.rol = "corredor"
                usuario.valido_por = request.user
                usuario.save()

            # Crear suscripción
            fecha_fin = timezone.now() + timezone.timedelta(days=30 * solicitud.plan.duracion_meses)
            SuscripcionCorredor.objects.update_or_create(
                corredor=usuario,
                defaults={
                    "plan": solicitud.plan,
                    "fecha_fin": fecha_fin,
                    "activa": True,
                },
            )

            solicitud.estado = "aprobada"
            solicitud.observaciones_admin = observaciones
            solicitud.revisado_por = request.user
            solicitud.fecha_revision = timezone.now()
            solicitud.save()

            # Notificar al postulante
            Communication.objects.create(
                recipient=usuario,
                emitter_user=request.user,
                source_type=SourceTypeChoices.SUPERADMIN if request.user.rol == "superadmin" else SourceTypeChoices.GERENTE,
                title="¡Postulación aprobada!",
                message=(
                    f"Tu postulación al plan {solicitud.plan.nombre} ha sido aprobada. "
                    f"Ya eres corredor de Serca Propiedades. Bienvenido al equipo.\n\n"
                    f"Observaciones: {observaciones or 'Ninguna'}"
                ),
                related_object_id=solicitud.id,
            )

            messages.success(
                request,
                f"Postulación APROBADA. {usuario.get_full_name()} ahora es corredor "
                f"(Plan: {solicitud.plan.nombre}). Se le ha notificado."
            )

        elif accion == "rechazar":
            solicitud.estado = "rechazada"
            solicitud.observaciones_admin = observaciones
            solicitud.revisado_por = request.user
            solicitud.fecha_revision = timezone.now()
            solicitud.save()

            if solicitud.usuario:
                Communication.objects.create(
                    recipient=solicitud.usuario,
                    emitter_user=request.user,
                    source_type=SourceTypeChoices.SUPERADMIN if request.user.rol == "superadmin" else SourceTypeChoices.GERENTE,
                    title="Postulación rechazada",
                    message=(
                        f"Lamentamos informarte que tu postulación al plan "
                        f"{solicitud.plan.nombre} ha sido rechazada.\n\n"
                        f"Observaciones: {observaciones or 'Sin observaciones'}"
                    ),
                    related_object_id=solicitud.id,
                )

            messages.warning(request, f"Postulación de {solicitud.nombres} {solicitud.apellidos} RECHAZADA.")

        elif accion == "en_dialogo":
            solicitud.estado = "en_dialogo"
            solicitud.observaciones_admin = observaciones
            solicitud.save()

            if solicitud.usuario:
                Communication.objects.create(
                    recipient=solicitud.usuario,
                    emitter_user=request.user,
                    source_type=SourceTypeChoices.SUPERADMIN if request.user.rol == "superadmin" else SourceTypeChoices.GERENTE,
                    title="Revisando tu postulación",
                    message=(
                        f"Estamos revisando tu postulación al plan {solicitud.plan.nombre}. "
                        f"Necesitamos lo siguiente: {observaciones or 'Contactarnos para más detalles.'}"
                    ),
                    related_object_id=solicitud.id,
                )

            messages.info(request, f"Postulación marcada como 'En diálogo'. Se notificó al postulante.")

        return redirect("revisar_postulaciones")

    # Obtener comunicaciones relacionadas a esta postulación
    comunicaciones = Communication.objects.filter(
        related_object_id=solicitud.id
    ).order_by("created_at") if solicitud.id else []

    return render(request, "detalle_postulacion.html", {
        "solicitud": solicitud,
        "comunicaciones": comunicaciones,
    })


# ============================================================
# GESTION VIEWS (mis_publicaciones, mis_asignadas, favoritas, precios, servicios)
# ============================================================

@login_required
def gestion_mis_publicaciones(request):
    from a03Prop.models import PublicacionProp, CorredorProp
    if request.user.rol in ("superadmin", "gerente"):
        publicaciones = PublicacionProp.objects.all().select_related('propiedad', 'publicante')
    elif request.user.rol == "corredor":
        props_ids = CorredorProp.objects.filter(corredor=request.user).values_list('propiedad_id', flat=True)
        publicaciones = PublicacionProp.objects.filter(publicante=request.user) | PublicacionProp.objects.filter(propiedad_id__in=props_ids)
        publicaciones = publicaciones.select_related('propiedad', 'publicante').distinct()
    else:
        publicaciones = PublicacionProp.objects.filter(publicante=request.user).select_related('propiedad', 'publicante')
    return render(request, "gestion_mis_publicaciones.html", {"publicaciones": publicaciones})

@login_required
def gestion_mis_asignadas(request):
    if request.user.rol == "base":
        messages.error(request, "No tienes acceso a esta sección.")
        return redirect("gestion")
    from a03Prop.models import CorredorProp, SolicitudPublicacion
    if request.user.rol == "corredor":
        asignaciones = CorredorProp.objects.filter(corredor=request.user).select_related('propiedad')
        solicitudes = SolicitudPublicacion.objects.filter(corredor_asignado=request.user).select_related('propiedad')
    else:
        asignaciones = CorredorProp.objects.all().select_related('propiedad', 'corredor')
        solicitudes = SolicitudPublicacion.objects.filter(corredor_asignado__isnull=False).select_related('propiedad', 'corredor_asignado')
    return render(request, "gestion_mis_asignadas.html", {"asignaciones": asignaciones, "solicitudes": solicitudes})

@login_required
def gestion_favoritas(request):
    from a03Prop.models import FavoritaProp
    favoritas_ids = FavoritaProp.objects.filter(usuario=request.user).values_list('propiedad_id', flat=True)
    favoritas = Propiedad.objects.filter(id__in=favoritas_ids).select_related('comuna')
    return render(request, "gestion_favoritas.html", {"favoritas": favoritas})

@login_required
def gestion_precios_publicacion(request):
    if request.user.rol not in ("superadmin", "gerente"):
        messages.error(request, "No tienes acceso a esta sección.")
        return redirect("gestion")
    from a03Prop.models import ConfiguracionPagoPubli
    config = ConfiguracionPagoPubli.objects.filter(activo=True).first()

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "actualizar" and config:
            config.banco_nombre = request.POST.get("banco_nombre", config.banco_nombre)
            config.tipo_cuenta = request.POST.get("tipo_cuenta", config.tipo_cuenta)
            config.numero_cuenta = request.POST.get("numero_cuenta", config.numero_cuenta)
            config.dni_titular = request.POST.get("dni_titular", config.dni_titular)
            config.titular = request.POST.get("titular", config.titular)
            config.email_confirmacion = request.POST.get("email_confirmacion", config.email_confirmacion)
            config.valor_pub_venta_mensual = int(request.POST.get("valor_pub_venta_mensual", config.valor_pub_venta_mensual))
            config.valor_destacado_venta_mensual = int(request.POST.get("valor_destacado_venta_mensual", config.valor_destacado_venta_mensual))
            config.valor_pub_arriendo_mensual = int(request.POST.get("valor_pub_arriendo_mensual", config.valor_pub_arriendo_mensual))
            config.valor_destacado_arriendo_mensual = int(request.POST.get("valor_destacado_arriendo_mensual", config.valor_destacado_arriendo_mensual))
            config.valor_pub_str_dia = int(request.POST.get("valor_pub_str_dia", config.valor_pub_str_dia))
            config.valor_destacado_str_dia = int(request.POST.get("valor_destacado_str_dia", config.valor_destacado_str_dia))
            config.save()
            messages.success(request, "✅ Valores de publicación actualizados correctamente.")
            return redirect("gestion_precios_publicacion")

        elif accion == "crear" and not config:
            config = ConfiguracionPagoPubli.objects.create(
                banco_nombre=request.POST.get("banco_nombre", ""),
                tipo_cuenta=request.POST.get("tipo_cuenta", "corriente"),
                numero_cuenta=request.POST.get("numero_cuenta", ""),
                dni_titular=request.POST.get("dni_titular", ""),
                titular=request.POST.get("titular", ""),
                email_confirmacion=request.POST.get("email_confirmacion", ""),
                valor_pub_venta_mensual=int(request.POST.get("valor_pub_venta_mensual", 4000)),
                valor_destacado_venta_mensual=int(request.POST.get("valor_destacado_venta_mensual", 6000)),
                valor_pub_arriendo_mensual=int(request.POST.get("valor_pub_arriendo_mensual", 5000)),
                valor_destacado_arriendo_mensual=int(request.POST.get("valor_destacado_arriendo_mensual", 3000)),
                valor_pub_str_dia=int(request.POST.get("valor_pub_str_dia", 5000)),
                valor_destacado_str_dia=int(request.POST.get("valor_destacado_str_dia", 3000)),
                activo=True,
            )
            messages.success(request, "✅ Configuración de precios creada exitosamente.")
            return redirect("gestion_precios_publicacion")

    return render(request, "gestion_precios.html", {"config": config})

@login_required
def gestion_servicios(request):
    if request.user.rol not in ("superadmin", "gerente"):
        messages.error(request, "No tienes acceso a esta sección.")
        return redirect("gestion")
    from a03Prop.models import ServiciosProp
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "crear":
            nombre = request.POST.get("nombre", "").strip()
            icono = request.POST.get("icono", "").strip()
            if nombre:
                ServiciosProp.objects.create(nombre=nombre, icono=icono)
                messages.success(request, f"Servicio '{nombre}' creado.")
        elif accion == "toggle":
            servicio_id = request.POST.get("servicio_id")
            from django.shortcuts import get_object_or_404
            servicio = get_object_or_404(ServiciosProp, id=servicio_id)
            servicio.is_active = not servicio.is_active
            servicio.save()
    servicios = ServiciosProp.objects.all().order_by("nombre")
    return render(request, "gestion_servicios.html", {"servicios": servicios})


# ============================================================
# CONFIRMACIÓN DE EMAIL
# ============================================================

def confirmar_email_view(request, uidb64, token):
    """
    Vista que procesa el enlace de confirmación de email.
    Si el token es válido y no ha expirado, marca email_confirmado = True.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and email_token_generator.check_token(user, token):
        if not user.email_confirmado:
            user.email_confirmado = True
            user.save(update_fields=["email_confirmado"])
            messages.success(
                request,
                "✅ ¡Correo electrónico confirmado exitosamente! Ya puedes disfrutar de todas las funcionalidades."
            )
        else:
            messages.info(request, "ℹ️ Tu correo ya estaba confirmado anteriormente.")
        return redirect("home")
    else:
        # Token inválido o expirado
        messages.error(
            request,
            "❌ El enlace de confirmación es inválido o ha expirado. "
            "Solicita un nuevo enlace desde tu perfil."
        )
        return redirect("home")


def serve_media_prod(request, path):
    """
    Sirve archivos media en producción (Railway no tiene nginx).
    Sin @login_required para que fotos de propiedades sean visibles públicamente.
    """
    from django.http import FileResponse, Http404
    import os
    from django.conf import settings
    
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    file_path = os.path.normpath(file_path)
    if not file_path.startswith(os.path.normpath(settings.MEDIA_ROOT)):
        raise Http404("Acceso denegado")
    if not os.path.exists(file_path):
        raise Http404("Archivo no encontrado")
    return FileResponse(open(file_path, 'rb'))


@login_required
def reenviar_confirmacion_simple(request):
    """
    Vista que intenta reenviar el correo de confirmación.
    Totalmente a prueba de fallos - nunca crashea porque no ejecuta
    código de email directamente; si hay error se muestra mensaje informativo
    y se redirige a home.
    """
    user = request.user
    email = user.email
    
    if not email:
        messages.info(
            request,
            "No tienes un email asociado a tu cuenta. "
            "Puedes seguir usando la plataforma con normalidad."
        )
        return redirect("home")
    
    if user.email_confirmado:
        messages.info(request, "ℹ️ Tu correo ya está confirmado. No necesitas reenviar.")
        return redirect("home")
    
    # Intentar envío en un bloque protegido que nunca puede crashear la vista
    try:
        enviado = send_confirmation_email(user)
        if enviado:
            messages.success(
                request,
                f"📧 Hemos reenviado el correo de confirmación a {email}. "
                "Revisa tu bandeja de entrada y también la carpeta de spam."
            )
            return redirect("home")
    except Exception:
        pass  # Falló el envío - mostramos mensaje informativo abajo
    
    # Si llegamos aquí: no se pudo enviar o hubo error
    messages.info(
        request,
        "📧 No pudimos enviar el correo de confirmación en este momento. "
        "No te preocupes, puedes seguir usando la plataforma con normalidad. "
        "Si necesitas ayuda, contáctanos por WhatsApp."
    )
    return redirect("home")


# ============================================================
# GESTIÓN DE INGRESOS (Cierre Económico por negocio)
# ============================================================

@login_required
def gestion_ingresos_view(request):
    """
    Panel de ingresos económicos por negocio cerrado.
    - Corredor: ve sus propios cierres. Puede perfeccionar (editar valores reales).
    - Gerente/Superadmin: ve todos + columna costo de publicación. Puede editar todo.
    """
    if request.user.rol not in ("corredor", "gerente", "superadmin"):
        messages.error(request, "No tienes permisos para acceder a esta sección.")
        return redirect("gestion")

    from django.db.models import Sum
    from a03Prop.models import CierreEconomico

    # === Filtros ===
    anio_filter = request.GET.get("anio", "")
    mes_filter = request.GET.get("mes", "")
    corredor_filter = request.GET.get("corredor", "")

    # Base queryset según rol
    if request.user.rol in ("gerente", "superadmin"):
        cierres_qs = CierreEconomico.objects.select_related(
            'propiedad', 'corredor', 'propiedad__comuna'
        )
        if corredor_filter:
            cierres_qs = cierres_qs.filter(corredor_id=corredor_filter)
    else:
        cierres_qs = CierreEconomico.objects.filter(
            corredor=request.user
        ).select_related('propiedad', 'propiedad__comuna')

    if anio_filter:
        cierres_qs = cierres_qs.filter(anio=int(anio_filter))
    if mes_filter:
        cierres_qs = cierres_qs.filter(mes=int(mes_filter))

    # Ordenar
    cierres = cierres_qs.order_by("-anio", "-mes", "-fecha_cierre")

    # === Totales ===
    totales = cierres.aggregate(
        total_bruto=Sum("comision_vendedor_presupuestada_clp") + Sum("comision_comprador_presupuestada_clp"),
    )

    # === Años disponibles para el filtro ===
    anos_disponibles = CierreEconomico.objects.values_list("anio", flat=True).distinct().order_by("-anio")
    if request.user.rol in ("gerente", "superadmin"):
        corredores_list = User.objects.filter(rol="corredor", is_active=True)
    else:
        corredores_list = []

    # === Propiedades cerradas SIN cierre económico (pendientes) ===
    from a03Prop.models import CorredorProp
    props_cerradas_ids = CierreEconomico.objects.values_list('propiedad_id', flat=True)
    
    if request.user.rol in ("gerente", "superadmin"):
        props_sin_cierre = Propiedad.objects.filter(
            tipo_cierre__isnull=False
        ).exclude(
            id__in=props_cerradas_ids
        ).select_related('comuna')
    else:
        # Corredor solo ve las que le asignaron
        mis_props_ids = CorredorProp.objects.filter(
            corredor=request.user, estado__in=["activa", "completada"]
        ).values_list('propiedad_id', flat=True)
        props_sin_cierre = Propiedad.objects.filter(
            id__in=mis_props_ids,
            tipo_cierre__isnull=False
        ).exclude(
            id__in=props_cerradas_ids
        ).select_related('comuna')

    return render(request, "gestion_ingresos.html", {
        "cierres": cierres,
        "props_sin_cierre": props_sin_cierre,
        "rol": request.user.rol,
        "es_admin": request.user.rol in ("gerente", "superadmin"),
        "anos_disponibles": anos_disponibles,
        "corredores_list": corredores_list,
        "filtro_anio": anio_filter,
        "filtro_mes": mes_filter,
        "filtro_corredor": corredor_filter,
        "meses_opciones": [
            (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
            (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
            (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
        ],
    })


@login_required
def crear_cierre_economico(request, prop_id):
    """
    Crea manualmente un CierreEconomico para una propiedad ya cerrada.
    Disponible para gerente/superadmin y corredor asignado.
    """
    from a03Prop.models import Propiedad, CorredorProp, CierreEconomico, PublicacionProp

    propiedad = get_object_or_404(Propiedad, id=prop_id)

    if not propiedad.tipo_cierre:
        messages.error(request, "La propiedad aún no está marcada como vendida/arrendada.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    # Verificar si ya tiene un cierre económico
    if CierreEconomico.objects.filter(propiedad=propiedad).exists():
        messages.warning(request, "Esta propiedad ya tiene un cierre económico registrado.")
        return redirect("gestion_ingresos")

    # Obtener corredor asignado
    cp = CorredorProp.objects.filter(propiedad=propiedad, estado="activa").select_related('corredor').first()
    if not cp:
        messages.error(request, "La propiedad no tiene un corredor asignado.")
        return redirect("detalle_propiedad", prop_id=prop_id)

    corredor = cp.corredor
    fecha_cierre = propiedad.fecha_cierre or timezone.now()

    if request.method == "POST":
        precio_venta = request.POST.get("precio_venta")
        moneda = request.POST.get("moneda_original", propiedad.tipo_moneda)
        pct_vendedor = request.POST.get("pct_comision_vendedor", cp.monto_comision_dueno or 0)
        pct_comprador = request.POST.get("pct_comision_comprador", cp.monto_comision_usu or 0)
        factor_uf = request.POST.get("factor_uf_clp") or None
        factor_usd = request.POST.get("factor_usd_clp") or None
        costo_pub = request.POST.get("costo_publicacion_clp") or None
        factor_uf_val = float(factor_uf) if factor_uf else None
        factor_usd_val = float(factor_usd) if factor_usd else None

        if not precio_venta:
            messages.error(request, "Debes indicar el precio de venta/arriendo.")
            return redirect("detalle_propiedad", prop_id=prop_id)

        precio_venta = float(precio_venta)
        pct_vendedor = float(pct_vendedor) if pct_vendedor else 0
        pct_comprador = float(pct_comprador) if pct_comprador else 0

        # Calcular precio en CLP
        precio_clp = precio_venta
        if moneda == "UF" and factor_uf_val:
            precio_clp = precio_venta * factor_uf_val
        elif moneda == "USD" and factor_usd_val:
            precio_clp = precio_venta * factor_usd_val

        # Calcular comisiones presupuestadas
        com_vendedor = precio_clp * pct_vendedor / 100
        com_comprador = precio_clp * pct_comprador / 100

        # Obtener datos del plan del corredor
        plan_nombre = ""
        tasa_serca = 0
        suscripcion = getattr(corredor, "suscripcion", None)
        if suscripcion and suscripcion.plan:
            plan_nombre = suscripcion.plan.nombre
            # comision_porcentaje es lo que RECIBE el corredor (ej: 70%). SERCA cobra 100 - ese valor.
            tasa_serca = 100.0 - float(suscripcion.plan.comision_porcentaje)

        CierreEconomico.objects.create(
            propiedad=propiedad,
            corredor=corredor,
            precio_venta=precio_venta,
            moneda_original=moneda,
            factor_uf_clp=factor_uf_val,
            factor_usd_clp=factor_usd_val,
            pct_comision_vendedor=pct_vendedor,
            pct_comision_comprador=pct_comprador,
            comision_vendedor_presupuestada_clp=com_vendedor,
            comision_comprador_presupuestada_clp=com_comprador,
            plan_nombre=plan_nombre,
            tasa_serca=tasa_serca,
            costo_publicacion_clp=float(costo_pub) if costo_pub else None,
            mes=fecha_cierre.month,
            anio=fecha_cierre.year,
            fecha_cierre=fecha_cierre,
        )

        messages.success(request, "✅ Cierre económico creado exitosamente.")
        return redirect("gestion_ingresos")

    # Pre-poblar campos para GET
    # Buscar costo de publicación
    try:
        solicitud = propiedad.solicitudes.filter(estado="publicada").first()
        costo_pub = float(solicitud.total_pago) if solicitud and solicitud.total_pago else None
    except Exception:
        costo_pub = None

    # Obtener datos del plan
    plan_nombre = ""
    tasa_serca = 0
    suscripcion = getattr(corredor, "suscripcion", None)
    if suscripcion and suscripcion.plan:
        plan_nombre = suscripcion.plan.nombre
        tasa_serca = 100.0 - float(suscripcion.plan.comision_porcentaje)

    # Buscar publicación asociada para precio publicado
    from a03Prop.models import PublicacionProp, ProcesoCompra
    publicacion = PublicacionProp.objects.filter(propiedad=propiedad, estado="publicada").first()
    
    # Buscar contratos asociados (arriendo o compraventa)
    from a03Prop.models import SolicitudVisita
    contratos_arriendo = SolicitudVisita.objects.filter(
        propiedad=propiedad,
        contrato_arriendo__isnull=False
    )
    from a03Prop.models import ProcesoCompra
    procesos_compra = ProcesoCompra.objects.filter(
        propiedad=propiedad,
        contrato_documento__isnull=False
    )

    return render(request, "crear_cierre_economico.html", {
        "propiedad": propiedad,
        "corredor": corredor,
        "cp": cp,
        "costo_pub": costo_pub,
        "plan_nombre": plan_nombre,
        "tasa_serca": tasa_serca,
        "fecha_cierre": fecha_cierre,
        "publicacion": publicacion,
        "contratos_arriendo": contratos_arriendo,
        "procesos_compra": procesos_compra,
    })


@login_required
def editar_cierre_economico(request, cierre_id):
    """
    Editar un CierreEconomico (perfeccionar valores reales).
    - Corredor: puede editar comisiones recibidas y por recibir.
    - Gerente/Superadmin: puede editar todo, incluyendo costo publicación.
    """
    from a03Prop.models import CierreEconomico
    cierre = get_object_or_404(CierreEconomico, id=cierre_id)

    es_admin = request.user.rol in ("gerente", "superadmin")
    es_corredor = request.user == cierre.corredor

    if not (es_admin or es_corredor):
        messages.error(request, "No tienes permiso para editar este cierre.")
        return redirect("gestion_ingresos")

    if request.method == "POST":
        accion = request.POST.get("accion", "")

        if accion == "perfeccionar":
            # Corredor: actualiza valores reales
            com_vend_rec = request.POST.get("comision_vendedor_recibida", "").strip()
            com_vend_pend = request.POST.get("comision_vendedor_por_recibir", "").strip()
            com_comp_rec = request.POST.get("comision_comprador_recibida", "").strip()
            com_comp_pend = request.POST.get("comision_comprador_por_recibir", "").strip()

            cierre.comision_vendedor_recibida = float(com_vend_rec) if com_vend_rec else None
            cierre.comision_vendedor_por_recibir = float(com_vend_pend) if com_vend_pend else None
            cierre.comision_comprador_recibida = float(com_comp_rec) if com_comp_rec else None
            cierre.comision_comprador_por_recibir = float(com_comp_pend) if com_comp_pend else None
            cierre.perfeccionado = True

        if es_admin:
            if request.POST.get("costo_publicacion_clp", "").strip():
                cierre.costo_publicacion_clp = float(request.POST.get("costo_publicacion_clp"))
            if request.POST.get("tasa_serca", "").strip():
                cierre.tasa_serca = float(request.POST.get("tasa_serca"))
            if request.POST.get("factor_uf_clp", "").strip():
                cierre.factor_uf_clp = float(request.POST.get("factor_uf_clp"))
            if request.POST.get("factor_usd_clp", "").strip():
                cierre.factor_usd_clp = float(request.POST.get("factor_usd_clp"))

        cierre.save()
        messages.success(request, "✅ Cierre económico actualizado.")
        return redirect("gestion_ingresos")

    # GET: renderizar formulario de edición
    return render(request, "editar_cierre_economico.html", {
        "cierre": cierre,
        "es_admin": es_admin,
    })


@login_required
def eliminar_cierre_economico(request, cierre_id):
    """Solo gerente/superadmin puede eliminar un cierre económico."""
    if request.user.rol not in ("gerente", "superadmin"):
        messages.error(request, "No tienes permiso para eliminar cierres.")
        return redirect("gestion_ingresos")

    from a03Prop.models import CierreEconomico
    cierre = get_object_or_404(CierreEconomico, id=cierre_id)
    cierre.delete()
    messages.success(request, "Cierre económico eliminado.")
    return redirect("gestion_ingresos")
