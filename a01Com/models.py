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
    related_object_type = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Tipo de objeto relacionado",
        help_text="'servicio' apunta al detalle de revisión de servicio; vacío/solicitud apunta al detalle de solicitud de propiedad.",
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


class ConsultaContacto(models.Model):
    """
    Log de consultas recibidas desde el botón de email del navbar.

    Permite llevar seguimiento de cada consulta (email, celular, mensaje),
    su estado (pendiente / respondida / cerrada) y la respuesta enviada.
    """
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("respondida", "Respondida"),
        ("cerrada", "Cerrada"),
    ]

    email = models.EmailField(verbose_name="Email del consultante")
    telefono = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Teléfono / Celular",
    )
    mensaje = models.TextField(verbose_name="Mensaje de consulta")
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="pendiente",
        verbose_name="Estado",
    )
    respuesta = models.TextField(
        blank=True,
        verbose_name="Respuesta enviada",
    )
    respondido_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Respondido el",
    )
    creado_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultas_contacto_enviadas",
        verbose_name="Creado por",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Consulta de contacto"
        verbose_name_plural = "Consultas de contacto"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Consulta #{self.id} - {self.email} ({self.get_estado_display()})"
