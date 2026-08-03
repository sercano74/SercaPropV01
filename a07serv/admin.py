from django.contrib import admin
from .models import CategoriaServicio, ServicioPublicitario, MensajeServicio, PagoServicio, CasoExito, RatingServicio


@admin.register(CategoriaServicio)
class CategoriaServicioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "icono", "orden", "is_active"]
    list_editable = ["orden", "is_active"]
    search_fields = ["nombre"]


@admin.register(ServicioPublicitario)
class ServicioPublicitarioAdmin(admin.ModelAdmin):
    list_display = ["titulo", "publicante", "categoria", "tipo_plan", "estado", "revisado_por", "fecha_expiracion", "dias_restantes"]
    list_filter = ["estado", "categoria", "tipo_plan"]
    search_fields = ["titulo", "publicante__email", "publicante__first_name"]
    date_hierarchy = "fecha_expiracion"
    raw_id_fields = ["publicante"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        ("Datos del servicio", {
            "fields": ("publicante", "categoria", "titulo", "descripcion", "imagen",
                       "sitio_web", "telefono_contacto", "email_contacto"),
        }),
        ("Plan y pago", {
            "fields": ("tipo_plan", "monto_pagado", "iva_incluido"),
        }),
        ("Publicación", {
            "fields": ("fecha_inicio", "fecha_expiracion", "estado"),
        }),
        ("Revisión", {
            "fields": ("revisado_por", "observaciones_admin"),
        }),
        ("Control", {
            "fields": ("renovacion_avisada", "created_at", "updated_at"),
        }),
    )


class MensajeServicioInline(admin.TabularInline):
    model = MensajeServicio
    extra = 0
    readonly_fields = ["nombre_remitente", "email_remitente", "telefono_remitente", "mensaje", "created_at"]
    can_delete = False


@admin.register(MensajeServicio)
class MensajeServicioAdmin(admin.ModelAdmin):
    list_display = ["servicio", "nombre_remitente", "email_remitente", "is_leido", "created_at"]
    list_filter = ["is_leido"]
    search_fields = ["nombre_remitente", "email_remitente", "servicio__titulo"]
    readonly_fields = ["created_at"]


@admin.register(PagoServicio)
class PagoServicioAdmin(admin.ModelAdmin):
    list_display = ["id", "servicio", "publicante", "tipo_pago", "monto_total", "estado", "created_at"]
    list_filter = ["estado", "tipo_pago"]
    search_fields = ["publicante__email"]


@admin.register(CasoExito)
class CasoExitoAdmin(admin.ModelAdmin):
    list_display = ["titulo", "servicio", "cliente_nombre", "is_publicado", "created_at"]
    list_filter = ["is_publicado"]


@admin.register(RatingServicio)
class RatingServicioAdmin(admin.ModelAdmin):
    list_display = ["servicio", "usuario", "puntaje", "created_at"]
    list_filter = ["puntaje"]
