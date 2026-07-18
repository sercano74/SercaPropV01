from django.contrib import admin
from .models import (
    ServiciosProp,
    Propiedad,
    FotosPropiedad,
    LegalDocsProp,
    LegalDocsUsu,
    CorredorProp,
    PublicacionProp,
    ConfiguracionPagoPubli,
)


class FotosPropiedadInline(admin.TabularInline):
    model = FotosPropiedad
    extra = 1


class LegalDocsPropInline(admin.TabularInline):
    model = LegalDocsProp
    extra = 0


class CorredorPropInline(admin.TabularInline):
    model = CorredorProp
    extra = 0


class PublicacionPropInline(admin.TabularInline):
    model = PublicacionProp
    extra = 0


@admin.register(ServiciosProp)
class ServiciosPropAdmin(admin.ModelAdmin):
    list_display = ["nombre", "icono", "is_active"]
    search_fields = ["nombre"]


@admin.register(Propiedad)
class PropiedadAdmin(admin.ModelAdmin):
    list_display = [
        "__str__",
        "dueno",
        "tipo_prop",
        "tipo_accion",
        "precio",
        "tipo_moneda",
        "estado",
    ]
    list_filter = ["tipo_prop", "tipo_accion", "tipo_uso", "estado", "comuna", "region"]
    search_fields = ["calle", "descripcion_propiedad", "dueno__username"]
    inlines = [
        FotosPropiedadInline,
        LegalDocsPropInline,
        CorredorPropInline,
        PublicacionPropInline,
    ]


@admin.register(FotosPropiedad)
class FotosPropiedadAdmin(admin.ModelAdmin):
    list_display = ["propiedad", "imagen"]
    search_fields = ["propiedad__calle"]


@admin.register(LegalDocsProp)
class LegalDocsPropAdmin(admin.ModelAdmin):
    list_display = ["nombre", "propiedad", "estado", "uploaded_at"]
    list_filter = ["estado"]
    search_fields = ["nombre", "propiedad__calle"]


@admin.register(LegalDocsUsu)
class LegalDocsUsuAdmin(admin.ModelAdmin):
    list_display = ["nombre", "usu", "propiedad", "estado", "uploaded_at"]
    list_filter = ["estado"]
    search_fields = ["nombre", "usu__username"]


@admin.register(CorredorProp)
class CorredorPropAdmin(admin.ModelAdmin):
    list_display = ["corredor", "propiedad", "tipo_comision", "estado"]
    list_filter = ["estado", "tipo_comision"]
    search_fields = ["corredor__username", "propiedad__calle"]


@admin.register(PublicacionProp)
class PublicacionPropAdmin(admin.ModelAdmin):
    list_display = [
        "propiedad",
        "publicante",
        "estado",
        "es_destacada",
        "meses",
        "total_pago",
        "inicia_at",
        "expira_at",
    ]
    list_filter = ["estado", "es_destacada"]
    search_fields = ["propiedad__calle", "publicante__username"]


@admin.register(ConfiguracionPagoPubli)
class ConfiguracionPagoPubliAdmin(admin.ModelAdmin):
    list_display = [
        "banco_nombre",
        "titular",
        "numero_cuenta",
        "activo",
    ]
