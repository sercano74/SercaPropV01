from django.contrib import admin
from .models import Communication


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
