from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Region,
    Comuna,
    User,
    Funcionario,
    AgendaCorredor,
    PlanSuscripcion,
    SuscripcionCorredor,
    SuscripcionVendedor,
    SolicitudCorredor,
    DocumentoGestion,
)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ["nombre"]
    search_fields = ["nombre"]


@admin.register(Comuna)
class ComunaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "region", "descripcion_seo"]
    list_filter = ["region"]
    search_fields = ["nombre", "region__nombre"]
    fieldsets = (
        (None, {"fields": ("nombre", "region", "slug")}),
        (
            "SEO Landing Page",
            {
                "classes": ("wide",),
                "description": (
                    "Texto único que la landing page mostrará al final. "
                    "Si lo dejas vacío se usa un texto genérico."
                ),
                "fields": ("descripcion_seo",),
            },
        ),
    )
    readonly_fields = ["slug"]


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        "username",
        "email",
        "rol",
        "dni",
        "cel_phone",
        "is_active",
        "email_confirmado",
    ]
    list_filter = ["rol", "is_active", "email_confirmado"]
    search_fields = ["username", "email", "dni", "cel_phone"]
    fieldsets = UserAdmin.fieldsets + (
        (
            "Información adicional",
            {
                "fields": (
                    "rol",
                    "dni",
                    "cel_phone",
                    "foto",
                    "domicilio",
                    "curriculo",
                    "comuna",
                    "valido_por",
                    "email_confirmado",
                )
            },
        ),
    )


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ["nombre_completo", "cargo", "orden", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["nombre_completo", "cargo"]
    list_editable = ["orden"]


@admin.register(AgendaCorredor)
class AgendaCorredorAdmin(admin.ModelAdmin):
    list_display = ["corredor", "fecha", "hora_inicio", "hora_fin", "activo", "cupos_por_hora"]
    list_filter = ["activo", "fecha"]
    search_fields = ["corredor__username", "corredor__email"]


@admin.register(PlanSuscripcion)
class PlanSuscripcionAdmin(admin.ModelAdmin):
    list_display = ["nombre", "tipo", "precio", "duracion_meses", "activo"]
    list_filter = ["tipo", "activo"]


@admin.register(SuscripcionCorredor)
class SuscripcionCorredorAdmin(admin.ModelAdmin):
    list_display = ["corredor", "plan", "fecha_inicio", "fecha_fin", "activa"]
    list_filter = ["activa"]
    search_fields = ["corredor__username"]


@admin.register(SuscripcionVendedor)
class SuscripcionVendedorAdmin(admin.ModelAdmin):
    list_display = ["vendedor", "plan", "fecha_inicio", "fecha_fin", "activa"]
    list_filter = ["activa"]
    search_fields = ["vendedor__username"]


@admin.register(SolicitudCorredor)
class SolicitudCorredorAdmin(admin.ModelAdmin):
    list_display = [
        "nombres", "apellidos", "email", "plan", "estado", "created_at"
    ]
    list_filter = ["estado", "plan"]
    search_fields = ["nombres", "apellidos", "email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DocumentoGestion)
class DocumentoGestionAdmin(admin.ModelAdmin):
    list_display = [
        "nombre", "categoria", "tipo_documento", "version", "activo",
        "descargas", "subido_por", "created_at",
    ]
    list_filter = ["categoria", "tipo_documento", "activo"]
    search_fields = ["nombre", "descripcion", "tags"]
    readonly_fields = ["descargas", "created_at", "updated_at"]
