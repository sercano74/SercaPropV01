from django.db import models


class ServiciosProp(models.Model):
    """Servicios o características de la propiedad o de su entorno."""
    nombre = models.CharField(max_length=100, verbose_name="Nombre del servicio")
    icono = models.CharField(max_length=50, blank=True, verbose_name="Icono (clase CSS/emoji)")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Servicio de propiedad"
        verbose_name_plural = "Servicios de propiedades"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Propiedad(models.Model):
    TIPO_PROP_CHOICES = [
        ("casa", "Casa"),
        ("departamento", "Departamento"),
        ("local", "Local Comercial"),
        ("terreno", "Terreno"),
        ("oficina", "Oficina"),
        ("bodega", "Bodega"),
        ("parcela", "Parcela"),
        ("otro", "Otro"),
    ]
    TIPO_USO_CHOICES = [
        ("habitacional", "Habitacional"),
        ("comercial", "Comercial"),
        ("agro", "Agrícola"),
    ]
    TIPO_ACCION_CHOICES = [
        ("venta", "Venta"),
        ("arriendo", "Arriendo"),
        ("srt", "Short Rental Time (SRT)"),
    ]
    TIPO_MONEDA_CHOICES = [
        ("PCL", "CLP"),
        ("UF", "UF"),
        ("USD", "USD"),
    ]
    ESTADO_CHOICES = [
        ("borrador", "Borrador"),
        ("publicada", "Publicada"),
        ("archivada", "Archivada"),
    ]

    dueno = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="propiedades",
        verbose_name="Dueño",
    )
    calle = models.CharField(max_length=255, verbose_name="Calle / Dirección")
    numero_calle = models.CharField(max_length=20, verbose_name="Número")
    tipo_prop = models.CharField(
        max_length=20, choices=TIPO_PROP_CHOICES, verbose_name="Tipo de propiedad"
    )
    num_tipo_prop = models.CharField(
        max_length=50, blank=True, verbose_name="Número / Identificación (Dpto, Lote, etc.)"
    )
    poblacion_localidad = models.CharField(
        max_length=255, blank=True, verbose_name="Población / Localidad"
    )
    comuna = models.ForeignKey(
        "a00seg.Comuna",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Comuna",
    )
    region = models.ForeignKey(
        "a00seg.Region",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Región",
    )
    numero_dormitorios = models.PositiveSmallIntegerField(default=0, verbose_name="N° Dormitorios")
    numero_banos = models.PositiveSmallIntegerField(default=0, verbose_name="N° Baños")
    descripcion_propiedad = models.TextField(blank=True, verbose_name="Descripción de la propiedad")
    descripcion_entorno = models.TextField(blank=True, verbose_name="Descripción del entorno")
    servicios_prop = models.ManyToManyField(
        ServiciosProp, blank=True, verbose_name="Servicios / Características"
    )
    tipo_uso = models.CharField(
        max_length=20, choices=TIPO_USO_CHOICES, default="habitacional", verbose_name="Tipo de uso"
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="borrador", verbose_name="Estado"
    )
    tipo_accion = models.CharField(
        max_length=20, choices=TIPO_ACCION_CHOICES, verbose_name="Tipo de acción"
    )
    tipo_moneda = models.CharField(
        max_length=5, choices=TIPO_MONEDA_CHOICES, default="PCL", verbose_name="Tipo de moneda"
    )
    precio = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio")
    m_construidos = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="M² construidos"
    )
    m_terreno = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="M² terreno"
    )
    tiene_bodega = models.BooleanField(default=False, verbose_name="¿Tiene bodega?")
    num_estacionamientos = models.PositiveSmallIntegerField(
        default=0, verbose_name="N° Estacionamientos"
    )
    montomensual_gastoscomunes_pcl = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Gastos comunes mensuales (CLP)"
    )
    montoanual_contribuciones_pcl = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Contribuciones anuales (CLP)"
    )
    # Cierre de operación (venta o arriendo)
    tipo_cierre = models.CharField(
        max_length=20,
        blank=True, null=True,
        choices=[("vendida", "Vendida"), ("arrendada", "Arrendada")],
        verbose_name="Tipo de cierre",
    )
    fecha_cierre = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de cierre")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Propiedad"
        verbose_name_plural = "Propiedades"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_tipo_prop_display()} - {self.calle} #{self.numero_calle} ({self.get_estado_display()})"

    def display_name_public(self):
        """Nombre público de la propiedad, sin dirección exacta (solo comuna + tipo)."""
        comuna_str = str(self.comuna) if self.comuna else "Sin comuna"
        return f"{self.get_tipo_prop_display()} - {comuna_str}"


class FotosPropiedad(models.Model):
    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.CASCADE, related_name="fotos", verbose_name="Propiedad"
    )
    imagen = models.ImageField(
        upload_to="propiedades/",
        verbose_name="Imagen",
    )

    class Meta:
        verbose_name = "Foto de propiedad"
        verbose_name_plural = "Fotos de propiedades"

    def __str__(self):
        return f"Foto de {self.propiedad}"


class LegalDocsProp(models.Model):
    """Documentos legales de la propiedad."""
    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.CASCADE, related_name="docs_legales", verbose_name="Propiedad"
    )
    nombre = models.CharField(max_length=255, verbose_name="Nombre del documento")
    documento = models.FileField(
        upload_to="docs_legales_prop/",
        verbose_name="Documento",
    )
    estado = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("aprobado", "Aprobado"),
            ("rechazado", "Rechazado"),
        ],
        default="pendiente",
        verbose_name="Estado",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Subido el")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")

    class Meta:
        verbose_name = "Documento legal de propiedad"
        verbose_name_plural = "Documentos legales de propiedades"

    def __str__(self):
        return f"{self.nombre} - {self.propiedad}"


class LegalDocsUsu(models.Model):
    """Documentos legales de usuarios asociados a una propiedad."""
    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.CASCADE, related_name="docs_usuarios", verbose_name="Propiedad"
    )
    usu = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        verbose_name="Usuario",
    )
    nombre = models.CharField(max_length=255, verbose_name="Nombre del documento")
    documento = models.FileField(
        upload_to="docs_legales_usu/",
        verbose_name="Documento",
    )
    estado = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("aprobado", "Aprobado"),
            ("rechazado", "Rechazado"),
        ],
        default="pendiente",
        verbose_name="Estado",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Subido el")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")

    class Meta:
        verbose_name = "Documento legal de usuario"
        verbose_name_plural = "Documentos legales de usuarios"

    def __str__(self):
        return f"{self.nombre} - {self.usu}"


class CorredorProp(models.Model):
    """Asignación de corredor a propiedad."""
    TIPO_COMISION_CHOICES = [
        ("porcentaje", "Porcentaje"),
        ("fijo", "Monto Fijo"),
    ]
    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.CASCADE, related_name="corredores", verbose_name="Propiedad"
    )
    corredor = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="propiedades_asignadas",
        verbose_name="Corredor",
    )
    tipo_comision = models.CharField(
        max_length=20, choices=TIPO_COMISION_CHOICES, default="porcentaje", verbose_name="Tipo de comisión"
    )
    monto_comision_usu = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Comisión (usuario)"
    )
    monto_comision_dueno = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Comisión (dueño)"
    )
    estado = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("activa", "Activa"),
            ("completada", "Completada"),
            ("cancelada", "Cancelada"),
        ],
        default="pendiente",
        verbose_name="Estado",
    )
    # Switches de permiso para editar datos de la propiedad
    corredor_puede_editar = models.BooleanField(
        default=True, verbose_name="Corredor puede editar propiedad",
        help_text="El gerente/superadmin activa esto para que el corredor pueda editar los datos"
    )
    dueno_puede_editar = models.BooleanField(
        default=True, verbose_name="Dueño puede editar propiedad",
        help_text="El corredor activa esto para que el dueño pueda editar los datos"
    )

    class Meta:
        verbose_name = "Corredor de propiedad"
        verbose_name_plural = "Corredores de propiedades"

    def __str__(self):
        return f"{self.corredor} → {self.propiedad}"


class PublicacionProp(models.Model):
    """Publicación de una propiedad en el portal."""
    ESTADO_CHOICES = [
        ("no_iniciada", "No iniciada"),
        ("en_revision", "En revisión"),
        ("objetada", "Objetada"),
        ("publicada", "Publicada"),
        ("renovada", "Renovada"),
        ("archivada", "Archivada"),
    ]
    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.CASCADE, related_name="publicaciones", verbose_name="Propiedad"
    )
    publicante = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="publicaciones",
        verbose_name="Publicante",
    )
    meses = models.PositiveIntegerField(default=1, verbose_name="Meses de publicación")
    es_destacada = models.BooleanField(default=False, verbose_name="¿Es destacada?")
    total_pago = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Total pagado"
    )
    comprobante = models.ImageField(
        upload_to="comprobantes/",
        blank=True,
        null=True,
        verbose_name="Comprobante de pago",
    )
    inicia_at = models.DateTimeField(blank=True, null=True, verbose_name="Inicia el")
    expira_at = models.DateTimeField(blank=True, null=True, verbose_name="Expira el")
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="no_iniciada", verbose_name="Estado"
    )
    renovacion_avisada = models.BooleanField(default=False, verbose_name="Renovación avisada")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Publicación de propiedad"
        verbose_name_plural = "Publicaciones de propiedades"

    def __str__(self):
        return f"Publicación {self.propiedad} - {self.get_estado_display()}"

    @property
    def dias_restantes(self):
        if not self.expira_at:
            return 0
        from django.utils import timezone
        delta = self.expira_at - timezone.now()
        return max(delta.days, 0)


class ConfiguracionPagoPubli(models.Model):
    """Configuración de valores de publicación y datos bancarios."""
    TIPO_CUENTA_CHOICES = [
        ("vista", "Cuenta Vista"),
        ("corriente", "Cuenta Corriente"),
        ("vale_vista", "Vale Vista"),
        ("otras", "Otras"),
    ]
    banco_nombre = models.CharField(max_length=120, verbose_name="Nombre del banco")
    tipo_cuenta = models.CharField(
        max_length=20, choices=TIPO_CUENTA_CHOICES, verbose_name="Tipo de cuenta"
    )
    numero_cuenta = models.CharField(max_length=50, verbose_name="Número de cuenta")
    dni_titular = models.CharField(max_length=20, verbose_name="RUT")
    titular = models.CharField(max_length=255, verbose_name="Titular")
    email_confirmacion = models.EmailField(verbose_name="Correo de confirmación")

    valor_pub_venta_mensual = models.PositiveIntegerField(
        default=4000, verbose_name="Valor publicación venta x mes"
    )
    valor_destacado_venta_mensual = models.PositiveIntegerField(
        default=6000, verbose_name="Valor destacado venta x mes"
    )
    valor_pub_arriendo_mensual = models.PositiveIntegerField(
        default=5000, verbose_name="Valor arriendo mensual"
    )
    valor_destacado_arriendo_mensual = models.PositiveIntegerField(
        default=3000, verbose_name="Valor arriendo destacado mensual"
    )
    valor_pub_str_dia = models.PositiveIntegerField(
        default=5000, verbose_name="Valor SRT x día"
    )
    valor_destacado_str_dia = models.PositiveIntegerField(
        default=3000, verbose_name="Valor SRT destacado x día"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Configuración de pago de publicación"
        verbose_name_plural = "Configuraciones de pago de publicaciones"

    def __str__(self):
        return f"Configuración de pagos - {self.banco_nombre} ({self.titular})"


# ============================================================
# CIERRE ECONÓMICO (Gestión de ingresos por negocio)
# ============================================================

class CierreEconomico(models.Model):
    """
    Registro económico de un negocio cerrado (venta o arriendo).
    Se crea automáticamente al marcar una propiedad como vendida/arrendada.
    Contiene las comisiones, el costo de publicación y el cálculo de
    comisión SERCA según el plan del corredor.

    El corredor puede "perfeccionar" editando los valores reales recibidos.
    El gerente/superadmin ve y puede editar todos los campos, incluyendo
    el costo de publicación.
    """
    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.CASCADE,
        related_name="cierres_economicos",
        verbose_name="Propiedad",
    )
    corredor = models.ForeignKey(
        "a00seg.User", on_delete=models.CASCADE,
        related_name="cierres_economicos",
        verbose_name="Corredor responsable",
    )

    # ===== Datos del negocio =====
    precio_venta = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Precio de venta/arriendo (nominal)",
    )
    moneda_original = models.CharField(
        max_length=5, choices=Propiedad.TIPO_MONEDA_CHOICES,
        default="PCL", verbose_name="Moneda original",
    )

    # Factores de conversión a CLP del día del cierre
    factor_uf_clp = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True,
        verbose_name="Valor UF → CLP",
        help_text="Valor de la UF en CLP a la fecha del cierre",
    )
    factor_usd_clp = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True,
        verbose_name="Valor USD → CLP",
        help_text="Valor del USD en CLP a la fecha del cierre",
    )

    # ===== Comisiones presupuestadas (desde CorredorProp / OG) =====
    pct_comision_vendedor = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="% Comisión vendedor",
    )
    pct_comision_comprador = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="% Comisión comprador",
    )
    comision_vendedor_presupuestada_clp = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Comisión vendedor presupuestada (CLP)",
    )
    comision_comprador_presupuestada_clp = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Comisión comprador presupuestada (CLP)",
    )

    # ===== Comisiones REALES (editables al perfeccionar) =====
    comision_vendedor_recibida = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Comisión vendedor RECIBIDA (CLP)",
        help_text="Valor real efectivamente recibido del vendedor",
    )
    comision_vendedor_por_recibir = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Comisión vendedor POR RECIBIR (CLP)",
        help_text="Saldo pendiente de recibir del vendedor",
    )
    comision_comprador_recibida = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Comisión comprador RECIBIDA (CLP)",
        help_text="Valor real efectivamente recibido del comprador",
    )
    comision_comprador_por_recibir = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Comisión comprador POR RECIBIR (CLP)",
        help_text="Saldo pendiente de recibir del comprador",
    )

    # ===== Datos del plan SERCA =====
    plan_nombre = models.CharField(
        max_length=50, blank=True,
        verbose_name="Nombre del plan del corredor",
    )
    tasa_serca = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Tasa comisión SERCA (%)",
        help_text="Porcentaje que SERCA cobra al corredor (del plan)",
    )

    # ===== Costo de publicación (solo visible gerente/superadmin) =====
    costo_publicacion_clp = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True,
        verbose_name="Costo de publicación (CLP)",
        help_text="Costo que SERCA erogó por la publicación",
    )

    # ===== Control =====
    mes = models.PositiveSmallIntegerField(verbose_name="Mes")
    anio = models.PositiveSmallIntegerField(verbose_name="Año")
    perfeccionado = models.BooleanField(
        default=False,
        verbose_name="Perfeccionado",
        help_text="Indica si el corredor ya ajustó los valores reales",
    )
    fecha_cierre = models.DateTimeField(verbose_name="Fecha de cierre")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cierre Económico"
        verbose_name_plural = "Cierres Económicos"
        ordering = ["-anio", "-mes"]

    def __str__(self):
        return f"Cierre #{self.id} - {self.propiedad} ({self.mes}/{self.anio})"

    # ===== Propiedades calculadas =====

    @property
    def precio_clp(self):
        """Precio convertido a CLP según la moneda original y factores del día."""
        if self.moneda_original == "PCL":
            return self.precio_venta
        elif self.moneda_original == "UF" and self.factor_uf_clp:
            return self.precio_venta * self.factor_uf_clp
        elif self.moneda_original == "USD" and self.factor_usd_clp:
            return self.precio_venta * self.factor_usd_clp
        return self.precio_venta

    @property
    def comision_vendedor_final_clp(self):
        """Comisión vendedor: real si perfeccionado, si no presupuestada."""
        return self.comision_vendedor_recibida or self.comision_vendedor_presupuestada_clp

    @property
    def comision_comprador_final_clp(self):
        """Comisión comprador: real si perfeccionado, si no presupuestada."""
        return self.comision_comprador_recibida or self.comision_comprador_presupuestada_clp

    @property
    def ingreso_bruto_clp(self):
        """Ingreso bruto total del corredor (vendedor + comprador)."""
        return self.comision_vendedor_final_clp + self.comision_comprador_final_clp

    @property
    def comision_serca_clp(self):
        """Comisión que SERCA cobra al corredor según su plan."""
        return self.ingreso_bruto_clp * self.tasa_serca / 100

    @property
    def ingreso_neto_corredor_clp(self):
        """Lo que realmente queda para el corredor después de comisión SERCA."""
        return self.ingreso_bruto_clp - self.comision_serca_clp

    @property
    def total_recibido_clp(self):
        """Suma de lo efectivamente recibido (vendedor + comprador)."""
        return (self.comision_vendedor_recibida or 0) + (self.comision_comprador_recibida or 0)

    @property
    def total_por_recibir_clp(self):
        """Suma de lo pendiente por recibir."""
        return (self.comision_vendedor_por_recibir or 0) + (self.comision_comprador_por_recibir or 0)


# ============================================================
# FAVORITAS
# ============================================================

class FavoritaProp(models.Model):
    """Relación de favoritos entre un usuario y una propiedad."""
    usuario = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="favoritas",
        verbose_name="Usuario",
    )
    propiedad = models.ForeignKey(
        Propiedad,
        on_delete=models.CASCADE,
        related_name="favoritada_por",
        verbose_name="Propiedad",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Agregada el")

    class Meta:
        verbose_name = "Favorita"
        verbose_name_plural = "Favoritas"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "propiedad"],
                name="unique_favorita_usuario_propiedad",
            )
        ]

    def __str__(self):
        return f"{self.usuario} ❤️ {self.propiedad}"


# ============================================================
# SOLICITUD DE VISITA
# ============================================================

class SolicitudVisita(models.Model):
    """
    Un usuario (no propietario) solicita visitar una propiedad
    en una hora disponible de la agenda del corredor.
    """
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente de confirmación"),
        ("aceptada", "Aceptada por el corredor"),
        ("rechazada", "Rechazada"),
        ("reprogramada", "Reprogramada (propuesta de nueva fecha)"),
        ("realizada", "Visita realizada"),
        ("cancelada", "Cancelada"),
    ]

    usuario = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="solicitudes_visita",
        verbose_name="Solicitante",
    )
    propiedad = models.ForeignKey(
        Propiedad,
        on_delete=models.CASCADE,
        related_name="solicitudes_visita",
        verbose_name="Propiedad",
    )
    corredor = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="visitas_asignadas",
        verbose_name="Corredor responsable",
    )
    # Bloque de agenda seleccionado
    bloque_agenda = models.ForeignKey(
        "a00seg.AgendaCorredor",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="visitas_solicitadas",
        verbose_name="Bloque de agenda seleccionado",
    )
    fecha_solicitada = models.DateField(verbose_name="Fecha solicitada")
    hora_inicio_solicitada = models.TimeField(verbose_name="Hora inicio solicitada")
    hora_fin_solicitada = models.TimeField(verbose_name="Hora fin solicitada")

    # Reprogramación (corredor propone nueva fecha)
    fecha_reprogramada = models.DateField(null=True, blank=True, verbose_name="Fecha reprogramada")
    hora_reprogramada_inicio = models.TimeField(null=True, blank=True, verbose_name="Hora reprogramada inicio")
    hora_reprogramada_fin = models.TimeField(null=True, blank=True, verbose_name="Hora reprogramada fin")
    mensaje_reprogramacion = models.TextField(blank=True, verbose_name="Mensaje de reprogramación")

    # Orden de Visita (PDF)
    orden_visita = models.FileField(
        upload_to="ordenes_visita/",
        blank=True, null=True,
        verbose_name="Orden de Visita (PDF)",
    )
    orden_visita_subida_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ordenes_visita_subidas",
        verbose_name="Subida por",
    )
    # Orden de Visita Firmada (PDF con firma del comprador)
    orden_visita_firmada = models.FileField(
        upload_to="ordenes_visita_firmadas/",
        blank=True, null=True,
        verbose_name="Orden de Visita Firmada (PDF)",
    )
    orden_visita_firmada_subida_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ordenes_visita_firmadas_subidas",
        verbose_name="OV Firmada subida por",
    )
    clausulas_aceptadas = models.BooleanField(default=False, verbose_name="Cláusulas de OV aceptadas")
    clausulas_aceptadas_at = models.DateTimeField(null=True, blank=True, verbose_name="Aceptadas el")

    # Motivo de rechazo (se guarda cuando el corredor/gerente rechaza)
    motivo_rechazo = models.TextField(blank=True, verbose_name="Motivo del rechazo")

# ===== FLUJO DE ARRIENDO =====
    intencion_arriendo = models.BooleanField(default=False, verbose_name="Intención de arriendo manifestada")
    intencion_arriendo_at = models.DateTimeField(null=True, blank=True, verbose_name="Intención manifestada el")

    # ===== DATOS DE COMISIÓN (rectificados en Contrato de Arriendo, usados en Cierre Económico) =====
    canon_arriendo_final = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Canon arriendo final (rectificado en Contrato)",
        help_text="Precio real del arriendo (puede diferir del publicado)",
    )
    tipo_comision_arrendador = models.CharField(
        max_length=20, blank=True,
        choices=[("porcentaje", "Porcentaje"), ("fijo", "Monto Fijo")],
        verbose_name="Tipo comisión arrendador (dueño)",
    )
    valor_comision_arrendador = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        verbose_name="Valor comisión arrendador (% o monto fijo)",
    )
    tipo_comision_arrendatario = models.CharField(
        max_length=20, blank=True,
        choices=[("porcentaje", "Porcentaje"), ("fijo", "Monto Fijo")],
        verbose_name="Tipo comisión arrendatario (usuario)",
    )
    valor_comision_arrendatario = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        verbose_name="Valor comisión arrendatario (% o monto fijo)",
    )
    tasa_serca_arriendo = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        verbose_name="Tasa SERCA arriendo (%)",
        help_text="Se pre-puebla desde OG, editable",
    )

    # Contrato de arriendo (PDF)
    contrato_arriendo = models.FileField(
        upload_to="contratos_arriendo/",
        blank=True, null=True,
        verbose_name="Contrato de arriendo (PDF)",
    )
    contrato_arriendo_subido_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="contratos_arriendo_subidos",
        verbose_name="Contrato subido por",
    )
    contrato_arriendo_ronda = models.PositiveIntegerField(default=0, verbose_name="Ronda de revisión (contrato)")
    contrato_aceptado_arrendador = models.BooleanField(default=False, verbose_name="Arrendador aceptó contrato")
    contrato_aceptado_arrendador_at = models.DateTimeField(null=True, blank=True)
    contrato_aceptado_arrendatario = models.BooleanField(default=False, verbose_name="Arrendatario aceptó contrato")
    contrato_aceptado_arrendatario_at = models.DateTimeField(null=True, blank=True)
    contrato_aceptado_at = models.DateTimeField(null=True, blank=True, verbose_name="Aceptado por ambos el")

    # Cita a notaría
    notaria_nombre = models.CharField(max_length=255, blank=True, verbose_name="Nombre de la notaría")
    notaria_direccion = models.CharField(max_length=255, blank=True, verbose_name="Dirección de la notaría")
    notaria_fecha = models.DateField(null=True, blank=True, verbose_name="Fecha notaría")
    notaria_hora = models.TimeField(null=True, blank=True, verbose_name="Hora notaría")
    notaria_aceptada_arrendador = models.BooleanField(default=False, verbose_name="Arrendador aceptó cita notarial")
    notaria_aceptada_arrendador_at = models.DateTimeField(null=True, blank=True)
    notaria_aceptada_arrendatario = models.BooleanField(default=False, verbose_name="Arrendatario aceptó cita notarial")
    notaria_aceptada_arrendatario_at = models.DateTimeField(null=True, blank=True)
    notaria_confirmada = models.BooleanField(default=False, verbose_name="Cita notarial confirmada (deprecated)")
    notaria_confirmada_at = models.DateTimeField(null=True, blank=True, verbose_name="Cita notarial confirmada el")

    # Cierre del caso
    caso_cerrado = models.BooleanField(default=False, verbose_name="Caso cerrado")
    caso_cerrado_at = models.DateTimeField(null=True, blank=True, verbose_name="Caso cerrado el")

    # ===== MECANISMO DE PAUSA (cuando otro comprador firma Promesa) =====
    pausado = models.BooleanField(default=False, verbose_name="Pausado por proceso de compra activo")
    pausado_por_proceso = models.ForeignKey(
        "ProcesoCompra",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="visitas_pausadas",
        verbose_name="Pausado por proceso",
    )

    # Control
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="pendiente", verbose_name="Estado"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de solicitud")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizada el")
    realizada_at = models.DateTimeField(null=True, blank=True, verbose_name="Realizada el")

    class Meta:
        verbose_name = "Solicitud de visita"
        verbose_name_plural = "Solicitudes de visitas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Visita #{self.id} - {self.usuario} → {self.propiedad} ({self.get_estado_display()})"

    # ------------------------------------------------------------------
    # URLs correctas para documentos PDF en Cloudinary
    # ------------------------------------------------------------------
    # cloudinary_storage a veces genera URLs con "image/upload" para PDFs
    # (o para archivos sin extensión), y Cloudinary responde 401 porque los
    # documentos se almacenan como tipo "raw". Estas propiedades corrigen
    # la URL para que use "raw/upload".
    # ------------------------------------------------------------------
    @staticmethod
    def _url_raw(url):
        if not url:
            return None
        if "/image/upload/" in url:
            return url.replace("/image/upload/", "/raw/upload/")
        return url

    @property
    def orden_visita_url(self):
        return self._url_raw(self.orden_visita.url if self.orden_visita else None)

    @property
    def orden_visita_firmada_url(self):
        return self._url_raw(self.orden_visita_firmada.url if self.orden_visita_firmada else None)


# ============================================================
# PROPUESTA DE COMPRA / ARRIENDO
# ============================================================

class PropuestaCompra(models.Model):
    """
    Propuesta de compra o arriendo que el visitante puede hacer
    después de realizada la visita.
    """
    TIPO_CHOICES = [
        ("compra", "Propuesta de Compra"),
        ("arriendo", "Propuesta de Arriendo"),
    ]
    solicitud_visita = models.OneToOneField(
        SolicitudVisita,
        on_delete=models.CASCADE,
        related_name="propuesta",
        verbose_name="Solicitud de visita",
    )
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de propuesta"
    )
    monto_ofrecido = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Monto ofrecido"
    )
    moneda = models.CharField(
        max_length=5, choices=Propiedad.TIPO_MONEDA_CHOICES, default="PCL", verbose_name="Moneda"
    )
    condiciones = models.TextField(blank=True, verbose_name="Condiciones / Detalles")
    nombre_comprador = models.CharField(max_length=255, verbose_name="Nombre del oferente")
    rut_comprador = models.CharField(max_length=20, verbose_name="RUT/DNI del oferente")
    email_comprador = models.EmailField(verbose_name="Email del oferente")
    telefono_comprador = models.CharField(max_length=20, verbose_name="Teléfono del oferente")

    estado = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente de revisión"),
            ("aceptada", "Aceptada"),
            ("rechazada", "Rechazada"),
            ("contra_oferta", "Contraoferta"),
        ],
        default="pendiente",
        verbose_name="Estado",
    )
    motivo_rechazo = models.TextField(
        blank=True, verbose_name="Motivo del rechazo",
        help_text="Razón por la que el dueño/corredor rechazó esta propuesta"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizada el")

    class Meta:
        verbose_name = "Propuesta"
        verbose_name_plural = "Propuestas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Propuesta #{self.id} ({self.get_tipo_display()}) - ${self.monto_ofrecido:,.0f}"


# ============================================================
# NUEVOS MODELOS PARA FLUJO DE PUBLICACIÓN EN 5 PASOS
# ============================================================

class SolicitudPublicacion(models.Model):
    """
    Solicitud de publicación que guía el flujo completo de 5 pasos:

    Paso 1 (usuario): Sube datos básicos propiedad + mínimo 3 fotos + escoge tipo
                       publicación (normal/destacada) + meses → sistema calcula costo
                       → sube comprobante → se crea propiedad (borrador) + solicitud (pago_revision)

    Paso 2 (gerente): Valida pago → asigna corredor → pasa a en_revision_corredor

    Paso 3 (corredor): Sube Orden de Gestión (define costo de su gestión + docs requeridos)
                        → pasa a og_pendiente

    Paso 4 (usuario): Acepta OG + completa datos (entorno, servicios, descripción)
                       + sube docs legales + si destacada, fotos restantes
                       → pasa a en_validacion

    Paso 5 (corredor): Valida en bucle con observaciones hasta aprobar → publica
    """
    ESTADO_CHOICES = [
        # Paso 1 - Datos básicos + pago
        ("pago_revision", "Pago en revisión"),
        ("pago_objetado", "Pago objetado"),
        # Paso 2 - Gerente aprueba y asigna corredor
        ("pago_aprobado", "Pago aprobado"),
        ("esperando_corredor", "Esperando asignación de corredor"),
        # Paso 3 - Corredor sube OG
        ("en_revision_corredor", "En revisión del corredor"),
        # Paso 4 - Usuario completa + acepta OG
        ("og_pendiente", "Orden de Gestión pendiente de aceptación"),
        # Paso 5 - Corredor valida en bucle
        ("en_validacion", "En validación final"),
        ("publicada", "Publicada"),
        ("rechazada", "Rechazada"),
        ("cancelada", "Cancelada"),
    ]

    usuario = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="solicitudes_publicacion",
        verbose_name="Solicitante",
    )
    meses = models.PositiveIntegerField(default=1, verbose_name="Meses de publicación")
    es_destacada = models.BooleanField(default=False, verbose_name="¿Destacada?")
    total_pago = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Total a pagar"
    )
    comprobante = models.ImageField(
        upload_to="comprobantes_solicitud/",
        blank=True, null=True,
        verbose_name="Comprobante de pago",
    )
    propiedad = models.ForeignKey(
        Propiedad,
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="solicitudes",
        verbose_name="Propiedad asociada",
    )
    corredor_asignado = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="solicitudes_publicacion_asignadas",
        verbose_name="Corredor asignado",
    )
    orden_gestion = models.FileField(
        upload_to="ordenes_gestion/",
        blank=True, null=True,
        verbose_name="Orden de Gestión (PDF)",
    )
    og_aceptada = models.BooleanField(default=False, verbose_name="Orden de Gestión aceptada")
    og_aceptada_at = models.DateTimeField(blank=True, null=True, verbose_name="Aceptada el")
    # Documentos requeridos que el corredor lista en la OG (separado por comas o JSON)
    # ===== DATOS DE COMISIÓN DESDE LA OG (para cierre económico) =====
    precio_referencia_og = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Precio referencia desde OG",
        help_text="Precio de venta o canon arriendo al momento de la OG",
    )
    tipo_comision_vendedor_og = models.CharField(
        max_length=20, blank=True,
        choices=[("porcentaje", "Porcentaje"), ("fijo", "Monto Fijo")],
        verbose_name="Tipo comisión vendedor (OG)",
    )
    valor_comision_vendedor_og = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        verbose_name="Valor comisión vendedor (OG) - % o monto fijo",
    )
    tipo_comision_comprador_og = models.CharField(
        max_length=20, blank=True,
        choices=[("porcentaje", "Porcentaje"), ("fijo", "Monto Fijo")],
        verbose_name="Tipo comisión comprador (OG)",
    )
    valor_comision_comprador_og = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        verbose_name="Valor comisión comprador (OG) - % o monto fijo",
    )
    tasa_serca_og = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        verbose_name="Tasa SERCA desde OG (%)",
        help_text="Se pre-puebla desde el plan del corredor, editable",
    )
    docs_requeridos = models.TextField(
        blank=True,
        verbose_name="Documentos requeridos",
        help_text="Lista de documentos que el usuario debe subir (separados por coma)",
    )
    estado = models.CharField(
        max_length=30, choices=ESTADO_CHOICES, default="pago_revision", verbose_name="Estado"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Solicitud de publicación"
        verbose_name_plural = "Solicitudes de publicación"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Solicitud #{self.id} - {self.usuario} ({self.get_estado_display()})"

    @property
    def paso_actual(self):
        """Retorna el número de paso (1-5) según el estado."""
        if self.estado in ("pago_revision", "pago_objetado"):
            return 1
        if self.estado in ("pago_aprobado", "esperando_corredor"):
            return 2
        if self.estado == "en_revision_corredor":
            return 3
        if self.estado in ("og_pendiente",):
            return 4
        if self.estado in ("en_validacion", "publicada"):
            return 5
        if self.estado in ("rechazada", "cancelada"):
            return 0
        return 0


class ObservacionSolicitud(models.Model):
    """
    Observaciones en el ciclo de ida y vuelta:
    - Paso 1: gerente ↔ usuario sobre el pago
    - Paso 4: corredor ↔ usuario sobre datos/OG
    """
    solicitud = models.ForeignKey(
        SolicitudPublicacion,
        on_delete=models.CASCADE,
        related_name="observaciones",
        verbose_name="Solicitud",
    )
    autor = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        verbose_name="Autor",
    )
    texto = models.TextField(verbose_name="Observación")
    archivo = models.FileField(
        upload_to="obs_solicitud/",
        blank=True, null=True,
        verbose_name="Archivo adjunto",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        verbose_name = "Observación de solicitud"
        verbose_name_plural = "Observaciones de solicitudes"
        ordering = ["created_at"]

    def __str__(self):
        return f"Obs #{self.id} - {self.autor} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"


# ============================================================
# PROCESO DE COMPRA-VENTA (POST-ACEPTACIÓN DE PROPUESTA)
# ============================================================

class ProcesoCompra(models.Model):
    """
    Proceso completo de compra-venta luego de que una PropuestaCompra es aceptada por el DUEÑO.

    Etapas:
    1. Propuesta aceptada → corredor sube Promesa de Compraventa
    2. Promesa en observación (ida y vuelta hasta que ambas partes aceptan)
    3. Promesa aceptada → corredor sube Instrucciones Notariales
    4. Instrucciones en observación → ambas partes aceptan
    5. Instrucciones aceptadas → corredor sube Contrato + datos notaría
    6. Contrato listo → firma notarial
    7. Inscripción en CBR → aprobado/rechazado → fin

    Una vez Promesa+Instrucciones aceptadas, todos los DEMÁS procesos/propuestas
    de la misma propiedad se PAUSAN. El corredor puede reactivar si el comprador no cumple.
    """
    ESTADO_CHOICES = [
        ("propuesta_aceptada", "Propuesta aceptada — Pendiente de Promesa de Compraventa"),
        ("promesa_observacion", "Promesa de Compraventa — En observaciones"),
        ("promesa_aceptada", "Promesa de Compraventa — Aceptada por ambas partes"),
        ("instrucciones_observacion", "Instrucciones Notariales — En observaciones"),
        ("instrucciones_aceptada", "Instrucciones Notariales — Aceptadas por ambas partes"),
        ("contrato_pendiente", "Pendiente de subir Contrato de Compraventa"),
        ("contrato_listo", "Contrato de Compraventa listo — Pendiente de firma notarial"),
        ("firma_notarial", "Firma notarial realizada"),
        ("escritura_cbr", "Escritura en inscripción en CBR"),
        ("escritura_aprobada", "Escritura inscrita — Operación finalizada"),
        ("escritura_rechazada", "Inscripción rechazada — Requiere gestión"),
        ("cancelado", "Proceso cancelado — Comprador no cumplió"),
        ("finalizado", "Proceso completado exitosamente"),
    ]

    propuesta = models.OneToOneField(
        PropuestaCompra,
        on_delete=models.CASCADE,
        related_name="proceso",
        verbose_name="Propuesta",
    )
    propiedad = models.ForeignKey(
        Propiedad,
        on_delete=models.CASCADE,
        related_name="procesos_compra",
        verbose_name="Propiedad",
    )
    comprador = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="compras",
        verbose_name="Comprador",
    )
    vendedor = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="ventas",
        verbose_name="Vendedor (Dueño)",
    )
    corredor = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        related_name="procesos_compra",
        verbose_name="Corredor responsable",
    )

    estado = models.CharField(
        max_length=30, choices=ESTADO_CHOICES, default="propuesta_aceptada", verbose_name="Estado"
    )

    # ----- Promesa de Compraventa -----
    promesa_documento = models.FileField(
        upload_to="promesas_compraventa/",
        blank=True, null=True,
        verbose_name="Documento de Promesa de Compraventa",
    )
    promesa_subido_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="promesas_subidas",
        verbose_name="Promesa subida por",
    )
    promesa_ronda = models.PositiveIntegerField(default=0, verbose_name="Ronda de observaciones (Promesa)")
    promesa_aceptado_vendedor = models.BooleanField(default=False, verbose_name="Vendedor aceptó Promesa")
    promesa_aceptado_vendedor_at = models.DateTimeField(null=True, blank=True)
    promesa_aceptado_comprador = models.BooleanField(default=False, verbose_name="Comprador aceptó Promesa")
    promesa_aceptado_comprador_at = models.DateTimeField(null=True, blank=True)
    promesa_aceptado_at = models.DateTimeField(null=True, blank=True, verbose_name="Aceptada por ambos el")

    # ----- Instrucciones Notariales -----
    instrucciones_documento = models.FileField(
        upload_to="instrucciones_notariales/",
        blank=True, null=True,
        verbose_name="Documento de Instrucciones Notariales",
    )
    instrucciones_subido_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="instrucciones_subidas",
        verbose_name="Instrucciones subidas por",
    )
    instrucciones_ronda = models.PositiveIntegerField(default=0, verbose_name="Ronda de observaciones (Instrucciones)")
    instrucciones_aceptado_vendedor = models.BooleanField(default=False)
    instrucciones_aceptado_vendedor_at = models.DateTimeField(null=True, blank=True)
    instrucciones_aceptado_comprador = models.BooleanField(default=False)
    instrucciones_aceptado_comprador_at = models.DateTimeField(null=True, blank=True)
    instrucciones_aceptado_at = models.DateTimeField(null=True, blank=True)

    # ----- Contrato de Compraventa -----
    contrato_documento = models.FileField(
        upload_to="contratos_compraventa/",
        blank=True, null=True,
        verbose_name="Documento de Contrato de Compraventa",
    )
    contrato_subido_por = models.ForeignKey(
        "a00seg.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="contratos_subidos",
        verbose_name="Contrato subido por",
    )
    contrato_firmado = models.BooleanField(default=False)
    contrato_firmado_at = models.DateTimeField(null=True, blank=True)

    # ===== DATOS DE COMISIÓN (rectificados en Promesa, usados en Cierre Económico) =====
    precio_venta_final = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        verbose_name="Precio venta final (rectificado en Promesa)",
        help_text="Precio real de la compraventa (puede diferir del publicado)",
    )
    tipo_moneda_final = models.CharField(
        max_length=5, blank=True, choices=Propiedad.TIPO_MONEDA_CHOICES,
        verbose_name="Moneda final",
    )
    tipo_comision_vendedor = models.CharField(
        max_length=20, blank=True,
        choices=[("porcentaje", "Porcentaje"), ("fijo", "Monto Fijo")],
        verbose_name="Tipo comisión vendedor",
    )
    valor_comision_vendedor = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        verbose_name="Valor comisión vendedor (% o monto fijo)",
    )
    tipo_comision_comprador = models.CharField(
        max_length=20, blank=True,
        choices=[("porcentaje", "Porcentaje"), ("fijo", "Monto Fijo")],
        verbose_name="Tipo comisión comprador",
    )
    valor_comision_comprador = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        verbose_name="Valor comisión comprador (% o monto fijo)",
    )
    tasa_serca = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        verbose_name="Tasa SERCA (%)",
        help_text="Se pre-puebla desde OG, editable por gerente",
    )
    # ----- Datos de Notaría -----
    notaria_nombre = models.CharField(max_length=255, blank=True, verbose_name="Nombre de la notaría")
    notaria_direccion = models.CharField(max_length=255, blank=True, verbose_name="Dirección de la notaría")
    notaria_fecha = models.DateField(null=True, blank=True, verbose_name="Fecha de firma notarial")
    notaria_hora = models.TimeField(null=True, blank=True, verbose_name="Hora de firma notarial")

    # ----- Inscripción en Conservador de Bienes Raíces -----
    escritura_ingresada_at = models.DateTimeField(null=True, blank=True, verbose_name="Ingresada a CBR el")
    escritura_resultado = models.CharField(
        max_length=20,
        choices=[("aprobada", "Aprobada"), ("rechazada", "Rechazada")],
        blank=True, null=True,
        verbose_name="Resultado de inscripción",
    )
    escritura_resultado_at = models.DateTimeField(null=True, blank=True)
    escritura_comunicado = models.BooleanField(default=False, verbose_name="Resultado comunicado a las partes")
    escritura_comunicado_at = models.DateTimeField(null=True, blank=True)

    # ----- Control de pausa de otros procesos -----
    otros_pausados = models.BooleanField(default=False, verbose_name="Otros procesos pausados")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")
    completado_at = models.DateTimeField(null=True, blank=True, verbose_name="Completado el")

    class Meta:
        verbose_name = "Proceso de Compra"
        verbose_name_plural = "Procesos de Compra"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Proceso #{self.id} - {self.propiedad} ({self.get_estado_display()})"

    def pausar_otros_procesos(self):
        """
        Pausa todas las demás solicitudes de visita y propuestas de la misma propiedad
        (excepto la que originó este proceso).
        """
        from django.utils import timezone
        # Pausar otras visitas de la misma propiedad (que no sean la de la propuesta ganadora)
        otras_visitas = SolicitudVisita.objects.filter(
            propiedad=self.propiedad,
            estado__in=["pendiente", "aceptada", "reprogramada", "realizada"],
        ).exclude(id=self.propuesta.solicitud_visita_id)

        ahora = timezone.now()
        for v in otras_visitas:
            v.pausado = True
            v.pausado_por_proceso = self
            v.save()

        self.otros_pausados = True
        self.save(update_fields=["otros_pausados", "updated_at"])

    def reactivar_otros_procesos(self):
        """
        Reactiva todos los procesos que fueron pausados por este proceso.
        """
        SolicitudVisita.objects.filter(
            pausado_por_proceso=self,
            pausado=True,
        ).update(pausado=False, pausado_por_proceso=None)

        self.otros_pausados = False
        self.save(update_fields=["otros_pausados", "updated_at"])


class ObservacionProceso(models.Model):
    """
    Observaciones en el flujo documental (Promesa / Instrucciones / Contrato).
    Cada documento puede tener múltiples rondas de observaciones hasta que ambas partes aceptan.
    """
    ETAPA_CHOICES = [
        ("promesa", "Promesa de Compraventa"),
        ("instrucciones", "Instrucciones Notariales"),
        ("contrato", "Contrato de Compraventa"),
    ]

    proceso = models.ForeignKey(
        ProcesoCompra,
        on_delete=models.CASCADE,
        related_name="observaciones",
        verbose_name="Proceso",
    )
    etapa = models.CharField(
        max_length=20, choices=ETAPA_CHOICES, verbose_name="Etapa"
    )
    ronda = models.PositiveIntegerField(default=1, verbose_name="N° de ronda")
    autor = models.ForeignKey(
        "a00seg.User",
        on_delete=models.CASCADE,
        verbose_name="Autor",
    )
    texto = models.TextField(verbose_name="Observación")
    archivo = models.FileField(
        upload_to="obs_proceso/",
        blank=True, null=True,
        verbose_name="Archivo adjunto",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        verbose_name = "Observación de proceso"
        verbose_name_plural = "Observaciones de procesos"
        ordering = ["etapa", "ronda", "created_at"]

    def __str__(self):
        return f"Obs #{self.id} - {self.get_etapa_display()} R{self.ronda} - {self.autor}"
