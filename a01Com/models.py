from django.db import models


class SourceTypeChoices(models.TextChoices):
    SISTEMA = "sistema", "Sistema"
    CORREDOR = "corredor", "Corredor"
    GERENTE = "gerente", "Gerente"
    SUPERADMIN = "superadmin", "Superadmin"
    USUARIO_BASE = "usuario_base", "Usuario Base"



class Communication(models.Model):
    recipient = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="comunicaciones_recibidas",
        verbose_name="Destinatario",
    )
    emitter_user = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="comunicaciones_enviadas",
        verbose_name="Emisor",
    )
    source_type = models.CharField(
        max_length=50,
        choices=SourceTypeChoices.choices,
        verbose_name="Tipo de comunicación",
    )
    title = models.CharField(max_length=255, verbose_name="Título")
    message = models.TextField(verbose_name="Mensaje")
    property_id = models.PositiveIntegerField(blank=True, null=True, verbose_name="ID propiedad")
    related_object_id = models.PositiveIntegerField(
        blank=True, null=True, verbose_name="ID objeto relacionado"
    )

    is_read = models.BooleanField(default=False, verbose_name="Leído")
    is_deleted = models.BooleanField(default=False, verbose_name="Eliminado")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Comunicación"
        verbose_name_plural = "Comunicaciones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_source_type_display()}: {self.title} → {self.recipient}"
