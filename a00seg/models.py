from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Region(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Región")

    class Meta:
        verbose_name = "Región"
        verbose_name_plural = "Regiones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Comuna(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Comuna")
    slug = models.SlugField(
        max_length=255, unique=True, blank=True, null=True,
        verbose_name="Slug SEO",
        help_text="URL amigable para landing pages por comuna. Se genera automáticamente.",
    )
    descripcion_seo = models.TextField(
        blank=True,
        verbose_name="Descripción SEO (landing page)",
        help_text="Texto único que aparece al final de la landing page de esta comuna. "
                  "Si está vacío se muestra un texto genérico. Escribe 2-3 frases que "
                  "describan la comuna: conectividad, comercio, colegios, parques, etc.",
    )
    region = models.ForeignKey(
        Region, 
        on_delete=models.CASCADE, 
        related_name="comunas", # Permite acceder a las comunas de una región con region.comunas.all()
        verbose_name="Región"
    )

    class Meta:
        verbose_name = "Comuna"
        verbose_name_plural = "Comunas"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre}, {self.region.nombre}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre) or f"comuna-{self.id}"
        super().save(*args, **kwargs)


class User(AbstractUser):
    ROL_CHOICES = [
        ("superadmin", "Superadmin"),
        ("gerente", "Gerente"),
        ("corredor", "Corredor"),
        ("base", "Usuario Base"),
    ]
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default="base", verbose_name="Rol")
    dni = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="RUT/DNI")
    cel_phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono celular")
    foto = models.ImageField(
        upload_to="usuarios/",
        blank=True,
        null=True,
        verbose_name="Foto",
    )
    domicilio = models.CharField(max_length=255, blank=True, verbose_name="Domicilio")
    curriculo = models.TextField(blank=True, verbose_name="Currículo")
    comuna = models.ForeignKey(
        Comuna, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Comuna"
    )
    valido_por = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Validado por",
        related_name="usuarios_validados",
    ) # Permite acceder a los usuarios validados por un usuario con user.usuarios_validados.all()
    email_confirmado = models.BooleanField(default=False, verbose_name="Email confirmado") # Permite filtrar usuarios con email confirmado usando User.objects.filter(email_confirmado=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"


class Funcionario(models.Model):
    nombre_completo = models.CharField(max_length=255, verbose_name="Nombre Completo")
    cargo = models.CharField(max_length=100, verbose_name="Cargo")
    imagen = models.ImageField(
        upload_to="funcionarios/",
        verbose_name="Imagen",
    )
    curriculo = models.TextField(verbose_name="Currículo/Biografía")
    linkedin = models.URLField(blank=True, null=True, verbose_name="LinkedIn")
    twitter = models.URLField(blank=True, null=True, verbose_name="Twitter")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Funcionario"
        verbose_name_plural = "Funcionarios"

    def __str__(self):
        return self.nombre_completo


class AgendaCorredor(models.Model):
    corredor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="agenda_visitas",
        verbose_name="Corredor",
    )
    fecha = models.DateField(default=timezone.localdate, verbose_name="Fecha")
    hora_inicio = models.TimeField(verbose_name="Hora inicio")
    hora_fin = models.TimeField(verbose_name="Hora fin")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    reservado = models.BooleanField(default=False, verbose_name="Reservado")
    cupos_por_hora = models.PositiveSmallIntegerField(default=1, verbose_name="Cupos por hora")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Agenda de corredor"
        verbose_name_plural = "Agendas de corredores"
        ordering = ["corredor_id", "fecha", "hora_inicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["corredor", "fecha", "hora_inicio", "hora_fin"],
                name="unique_agenda_corredor_bloque",
            )
        ]

    def __str__(self):
        return f"{self.corredor} - {self.fecha} {self.hora_inicio}-{self.hora_fin}"

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError("La hora fin debe ser posterior a la hora inicio.")

    def save(self, *args, **kwargs):
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora fin debe ser posterior a la hora inicio.")
        super().save(*args, **kwargs)

    @property
    def duracion_minutos(self):
        start_minutes = self.hora_inicio.hour * 60 + self.hora_inicio.minute
        end_minutes = self.hora_fin.hour * 60 + self.hora_fin.minute
        return max(end_minutes - start_minutes, 0)


class PlanSuscripcion(models.Model):
    TIPO_CHOICES = [
        ("corredor", "Corredor"),
        ("vendedor", "Vendedor (Usuario Base)"),
    ]
    nombre = models.CharField(max_length=50, verbose_name="Nombre del plan")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="corredor", verbose_name="Tipo de plan")
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio")
    duracion_meses = models.IntegerField(default=1, verbose_name="Duración (meses)")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    max_propiedades_simultaneas = models.PositiveSmallIntegerField(
        default=5, verbose_name="Máx. propiedades simultáneas"
    )
    comision_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=60.00,
        verbose_name="Comisión (%)",
        help_text="Porcentaje de comisión que recibe el corredor"
    )

    class Meta:
        verbose_name = "Plan de suscripción"
        verbose_name_plural = "Planes de suscripción"

    def __str__(self):
        return f"{self.nombre} - ${self.precio} / {self.duracion_meses} mes(es)"


class SuscripcionCorredor(models.Model):
    corredor = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="suscripcion", verbose_name="Corredor"
    )
    plan = models.ForeignKey(PlanSuscripcion, on_delete=models.PROTECT, verbose_name="Plan")
    fecha_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de inicio")
    fecha_fin = models.DateTimeField(verbose_name="Fecha de término")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    renovacion_avisada = models.BooleanField(default=False, verbose_name="Renovación avisada")

    class Meta:
        verbose_name = "Suscripción de corredor"
        verbose_name_plural = "Suscripciones de corredores"

    def __str__(self):
        estado = "Activa" if self.activa else "Inactiva"
        return f"{self.corredor} - {self.plan.nombre} ({estado})"

    @property
    def dias_restantes(self):
        if not self.fecha_fin:
            return 0
        delta = self.fecha_fin - timezone.now()
        return max(delta.days, 0)


class SuscripcionVendedor(models.Model):
    vendedor = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="suscripcion_vendedor", verbose_name="Vendedor"
    )
    plan = models.ForeignKey(PlanSuscripcion, on_delete=models.PROTECT, verbose_name="Plan")
    fecha_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de inicio")
    fecha_fin = models.DateTimeField(verbose_name="Fecha de término")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    renovacion_avisada = models.BooleanField(default=False, verbose_name="Renovación avisada")

    class Meta:
        verbose_name = "Suscripción de vendedor"
        verbose_name_plural = "Suscripciones de vendedores"

    def __str__(self):
        estado = "Activa" if self.activa else "Inactiva"
        return f"{self.vendedor} - {self.plan.nombre} ({estado})"

    @property
    def dias_restantes(self):
        if not self.fecha_fin:
            return 0
        delta = self.fecha_fin - timezone.now()
        return max(delta.days, 0)


class SolicitudCorredor(models.Model):
    """Postulación de un usuario para convertirse en corredor."""
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("en_dialogo", "En diálogo"),
        ("aprobada", "Aprobada"),
        ("rechazada", "Rechazada"),
    ]

    # Si el usuario ya tenía cuenta, se vincula; si no, se crea al aprobar
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name="solicitudes_corredor", verbose_name="Usuario (si ya tenía cuenta)"
    )

    # Datos personales (para postulantes nuevos o para actualizar)
    nombres = models.CharField(max_length=255, verbose_name="Nombres")
    apellidos = models.CharField(max_length=255, verbose_name="Apellidos")
    email = models.EmailField(verbose_name="Email")
    dni = models.CharField(max_length=20, blank=True, verbose_name="RUT/DNI")
    cel_phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono celular")
    domicilio = models.CharField(max_length=255, blank=True, verbose_name="Domicilio")
    curriculo = models.TextField(blank=True, verbose_name="Currículo / Experiencia")
    comuna = models.ForeignKey(
        Comuna, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Comuna"
    )

    # Plan escogido y comprobante
    plan = models.ForeignKey(
        PlanSuscripcion, on_delete=models.PROTECT, verbose_name="Plan seleccionado"
    )
    comprobante = models.ImageField(
        upload_to="comprobantes_corredor/", verbose_name="Comprobante de depósito"
    )

    # Estado y revisión
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="pendiente", verbose_name="Estado"
    )
    observaciones_admin = models.TextField(
        blank=True, verbose_name="Observaciones del administrador"
    )
    revisado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="solicitudes_revisadas", verbose_name="Revisado por"
    )
    fecha_revision = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de revisión")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de postulación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        verbose_name = "Solicitud de corredor"
        verbose_name_plural = "Solicitudes de corredores"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Solicitud de {self.nombres} {self.apellidos} - {self.get_estado_display()}"
