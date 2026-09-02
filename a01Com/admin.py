from django.contrib import admin
from .models import Communication, ConsultaContacto


@admin.register(Communication)
class CommunicationAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "recipient",
        "emitter_user",
        "source_type",
        "is_read",
        "created_at",
    ]
    list_filter = ["source_type", "is_read"]
    search_fields = ["title", "message", "recipient__username", "emitter_user__username"]


@admin.register(ConsultaContacto)
class ConsultaContactoAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "email",
        "telefono",
        "estado",
        "created_at",
        "respondido_at",
    ]
    list_filter = ["estado", "created_at"]
    search_fields = ["email", "telefono", "mensaje", "respuesta"]
    readonly_fields = ["created_at", "updated_at"]
