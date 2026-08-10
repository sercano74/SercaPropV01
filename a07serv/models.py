from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class CategoriaServicio(models.Model):
    """Categorías de servicios de construcción (cerámica, gasfiter, electricista, etc.)"""
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la categoría")
    icono = models.CharField(max_length=50, blank=True, verbose_name="Icono (emoji/clase CSS)")
    orden = models.PositiveSmallIntegerField(default=0, verbose_name="Orden de aparición")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Categoría de servicio"
        verbose_name_plural = "Categorías de servicios"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return f"{self.icono or '🔧'} {self.nombre}"


class ServicioPublicitario(models.Model):
    """
    Servicio publicitario publicado por un prestador (publicante) que ha pagado.
    Similar a PublicacionProp pero para servicios de construcción.

    Flujo de revisión:
    - en_revision: el servicio fue contratado y subido por el publicante pero aún
      NO está publicado. El gerente/superadmin debe validar contenido y pago.
    - objetado: el gerente detectó una discrepancia en contenido o pago.
      El servicio NO aparece en el directorio hasta ser publicado.
    - activo: el gerente aprobó y "inició la publicación".
    """
    ESTADO_CHOICES = [
        ("en_revision", "En revisión"),
        ("objetado", "Objetado"),
        ("activo", "Activo"),
        ("pausado", "Pausado"),
        ("expirado", "Expirado"),
        ("cancelado", "Cancelado"),
    ]

    publicante = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="servicios_publicitarios",
        verbose_name="Publicante (prestador)",
    )
    categoria = models.ForeignKey(
        CategoriaServicio,
        on_delete=models.PROTECT,
        related_name="servicios",
        verbose_name="Categoría",
    )
    titulo = models.CharField(max_length=200, verbose_name="Título del servicio")
    descripcion = models.TextField(verbose_name="Descripción del servicio")
    imagen = models.ImageField(
        upload_to="servicios/",
        verbose_name="Imagen del servicio",
    )
    sitio_web = models.URLField(blank=True, verbose_name="Sitio web del publicante")
    telefono_contacto = models.CharField(max_length=20, blank=True, verbose_name="Teléfono de contacto")
    email_contacto = models.EmailField(blank=True, verbose_name="Email de contacto")

    # Plan de pago
    tipo_plan = models.CharField(
        max_length=10,
        choices=[("mensual", "Mensual"), ("anual", "Anual")],
        verbose_name="Tipo de plan",
    )
    monto_pagado = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Monto pagado"
    )
    iva_incluido = models.BooleanField(default=True, verbose_name="IVA incluido en el monto")
    fecha_inicio = models.DateTimeField(default=timezone.now, verbose_name="Fecha de inicio")
    fecha_expiracion = models.DateTimeField(
        blank=True, null=True, verbose_name="Fecha de expiración",
        help_text="Se asigna cuando el gerente aprueba e inicia la publicación.",
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="en_revision", verbose_name="Estado"
    )

    # Revisión del gerente/superadmin
    revisado_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="servicios_revisados",
        verbose_name="Revisado por",
    )
    observaciones_admin = models.TextField(
        blank=True, verbose_name="Observaciones / motivo de objeción"
    )

    # Control
    renovacion_avisada = models.BooleanField(default=False, verbose_name="Renovación avisada")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Servicio publicitario"
        verbose_name_plural = "Servicios publicitarios"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.titulo} - {self.publicante.get_full_name() or self.publicante.email} ({self.get_estado_display()})"

    @property
    def dias_restantes(self):
        if not self.fecha_expiracion:
            return 0
        delta = self.fecha_expiracion - timezone.now()
        return max(delta.days, 0)

    @property
    def rating_promedio(self):
        ratings = self.ratings.all()
        if not ratings:
            return 0
        return round(sum(r.puntaje for r in ratings) / ratings.count(), 1)

    @property
    def cantidad_ratings(self):
        return self.ratings.count()


class MensajeServicio(models.Model):
    """
    Mensaje que un usuario envía al publicante de un servicio.
    El publicante gestiona estos mensajes en su panel y en el detalle del servicio.

    - `remitente`: usuario autenticado que escribió el mensaje (None si fue anónimo).
    - `destinatario`: publicante del servicio (copia de servicio.publicante para
      consultas rápidas por usuario).
    El publicante puede ver todos los mensajes de su servicio; un usuario autenticado
    solo puede ver los mensajes que él mismo envió (remitente=usuario) y las
    respuestas que el publicante le dio.
    """
    servicio = models.ForeignKey(
        ServicioPublicitario,
        on_delete=models.CASCADE,
        related_name="mensajes",
        verbose_name="Servicio",
    )
    remitente = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="mensajes_servicios_enviados",
        verbose_name="Remitente (usuario autenticado)",
        help_text="Usuario autenticado que envió el mensaje. Null si fue anónimo.",
    )
    destinatario = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="mensajes_servicios_recibidos",
        verbose_name="Destinatario (publicante)",
        help_text="Publicante del servicio que recibe el mensaje.",
    )
    nombre_remitente = models.CharField(max_length=255, verbose_name="Nombre completo")
    email_remitente = models.EmailField(verbose_name="Email")
    telefono_remitente = models.CharField(max_length=20, verbose_name="Teléfono")
    mensaje = models.TextField(verbose_name="Mensaje / Requerimiento")

    is_leido = models.BooleanField(default=False, verbose_name="Leído por el publicante")
    leido_at = models.DateTimeField(blank=True, null=True, verbose_name="Leído el")
    respuesta = models.TextField(blank=True, verbose_name="Respuesta del publicante")
    respondido_at = models.DateTimeField(blank=True, null=True, verbose_name="Respondido el")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de envío")

    class Meta:
        verbose_name = "Mensaje de servicio"
        verbose_name_plural = "Mensajes de servicios"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["servicio", "remitente"], name="msg_serv_rem_idx"),
            models.Index(fields=["servicio", "email_remitente"], name="msg_serv_email_idx"),
        ]

    def __str__(self):
        return f"Mensaje de {self.nombre_remitente} → {self.servicio.titulo}"


class PagoServicio(models.Model):
    """
    Registro de pago de un servicio publicitario.
    Similar al sistema de pagos de a03Prop.
    """
    TIPO_PAGO_CHOICES = [
        ("mensual", "Mensual (CLP $4.200 + IVA)"),
        ("anual", "Anual (CLP $39.800 + IVA)"),
    ]
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente de revisión"),
        ("aprobado", "Aprobado"),
        ("rechazado", "Rechazado"),
    ]

    servicio = models.ForeignKey(
        ServicioPublicitario,
        on_delete=models.CASCADE,
        related_name="pagos",
        verbose_name="Servicio",
    )
    publicante = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="pagos_servicios",
        verbose_name="Publicante",
    )
    tipo_pago = models.CharField(
        max_length=10, choices=TIPO_PAGO_CHOICES, verbose_name="Tipo de pago"
    )
    monto_base = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Monto base"
    )
    monto_iva = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="IVA (19%)"
    )
    monto_total = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Monto total"
    )
    comprobante = models.ImageField(
        upload_to="comprobantes_servicios/",
        verbose_name="Comprobante de pago",
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="pendiente", verbose_name="Estado"
    )
    revisado_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="pagos_servicios_revisados",
        verbose_name="Revisado por",
    )
    observaciones_admin = models.TextField(blank=True, verbose_name="Observaciones del admin")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de pago")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Pago de servicio"
        verbose_name_plural = "Pagos de servicios"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pago #{self.id} - {self.get_tipo_pago_display()} - ${self.monto_total:,.0f}"


class CasoExito(models.Model):
    """
    Casos de éxito que SERCA administra para mostrar en el directorio.
    Pueden estar asociados a un servicio de construcción o a una propiedad vendida/arrendada.
    Ayudan a generar confianza en los servicios publicados y propiedades gestionadas.
    """
    servicio = models.ForeignKey(
        ServicioPublicitario,
        on_delete=models.CASCADE,
        blank=True, null=True,
        related_name="casos_exito",
        verbose_name="Servicio (opcional)",
    )
    propiedad = models.ForeignKey(
        "a03Prop.Propiedad",
        on_delete=models.CASCADE,
        blank=True, null=True,
        related_name="casos_exito",
        verbose_name="Propiedad (opcional)",
    )
    titulo = models.CharField(max_length=255, verbose_name="Título del caso")
    descripcion = models.TextField(verbose_name="Descripción / Testimonio")
    imagen_antes = models.ImageField(
        upload_to="casos_exito/",
        blank=True, null=True,
        verbose_name="Imagen 'Antes'",
    )
    imagen_despues = models.ImageField(
        upload_to="casos_exito/",
        blank=True, null=True,
        verbose_name="Imagen 'Después'",
    )
    cliente_nombre = models.CharField(max_length=255, verbose_name="Nombre del cliente")
    cliente_testimonio = models.TextField(blank=True, verbose_name="Testimonio del cliente")
    is_publicado = models.BooleanField(default=True, verbose_name="Publicado")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Caso de éxito"
        verbose_name_plural = "Casos de éxito"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.titulo} - {self.servicio.titulo}"

class ConfiguracionPrecioServicio(models.Model):
    """Configuración de precios de publicación de servicios de construcción."""
    valor_mensual = models.PositiveIntegerField(
        default=4200, verbose_name="Valor plan mensual (CLP)"
    )
    valor_anual = models.PositiveIntegerField(
        default=39800, verbose_name="Valor plan anual (CLP)"
    )
    iva = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.19, verbose_name="IVA (decimal)"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")

    class Meta:
        verbose_name = "Configuración de precio de servicio"
        verbose_name_plural = "Configuraciones de precios de servicios"

    def __str__(self):
        return f"Precios: Mensual ${self.valor_mensual:,} / Anual ${self.valor_anual:,}"


class RatingServicio(models.Model):
    """
    Calificación que un usuario deja al prestador del servicio.
    Sistema de 1 a 5 estrellas.
    """
    servicio = models.ForeignKey(
        ServicioPublicitario,
        on_delete=models.CASCADE,
        related_name="ratings",
        verbose_name="Servicio",
    )
    usuario = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        blank=True, null=True,
        verbose_name="Usuario (anónimo si no autenticado)",
    )
    nombre_mostrar = models.CharField(
        max_length=100, blank=True, verbose_name="Nombre a mostrar"
    )
    puntaje = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Puntaje (1-5)",
    )
    comentario = models.TextField(blank=True, verbose_name="Comentario")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        verbose_name = "Calificación de servicio"
        verbose_name_plural = "Calificaciones de servicios"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["servicio", "usuario"],
                name="unique_rating_servicio_usuario",
            )
        ]

    def __str__(self):
        return f"{'⭐' * self.puntaje} - {self.servicio.titulo}"
