# Plan: Publicación por representación

**Un corredor, gerente o superadmin publica una propiedad en nombre de un propietario que queda fuera de la plataforma, con mandato firmado obligatorio, doble control del gerente, condiciones económicas capturadas en la Orden de Gestión y aviso al propietario con ventana de objeción.**

> Estado: **listo para implementar**. No se ha tocado código de producción.
> Proyecto: **SercaProp** (`propiedades.serca.online`). Apps `a00seg`, `a01Com`, `a03Prop`, `a07serv`.
> Revisión del código: **30-09-2026**. Los números de línea corresponden a esa revisión.
>
> **Advertencia sobre datos:** el `db.sqlite3` local es un snapshot de desarrollo, **no** la base de producción. Los valores autoritativos de los planes se leen de producción.

---

## 0. Decisiones cerradas

| # | Decisión | Resultado |
|---|---|---|
| A | ¿El propietario entra a la plataforma? | **No.** Sin cuenta, sin contraseña, sin bandeja |
| B | ¿Cómo se controla la representación? | **Doble control del gerente**: valida el mandato en la etapa 2 y aprueba la OG en la etapa 3 |
| C | ¿Se avisa al propietario? | **Sí**: un correo al email declarado, con enlace para objetar |
| D | Cupo por plan | **Mensual calendario**: 5 (Barrio), 15 (Metrópoli) |
| E | `Propiedad.dueno` | **Nullable** (`SET_NULL`), más `representante` y datos declarados |
| F | Orden de Gestión | Se sube en la etapa 2, con cláusula de representación, y la aprueba el gerente |
| G | Ventana de objeción | **Obligatoria**: mínimo 1, máximo 7, por defecto 1 |
| H | Tipos de mandato | `verbal` sólo gerente y superadmin; el agente senior con `escrito` o `notarial` |
| I | Alcance del cupo | Toda la producción del corredor en el mes, propia o en representación |
| J | Productos | Primero venta; arriendo y SRT después |
| K | Cierres históricos | Se corrigen sólo hacia adelante |
| L | ¿Puede el gerente autoaprobarse? | **Sí**, con marca de auditoría |
| M | Pago | Lo eroga el propietario o el corredor; **sube el comprobante el solicitante** |
| N | Aviso con copia oculta | Al propietario; **CCO a gerente y superadmin**; se informa al representante antes |
| O | Comisiones de la OG | **Se capturan como inputs** al subir la OG, en ambos flujos |
| P | Vestigios de planes | Se elimina el bloque muerto de `planes.html` |
| Q | **Fiscalización de comisiones** | **Diferenciada por rol**: gerente sin fiscalización; los demás roles con criterios de trazabilidad |
| R | **Cierre económico** | Debe soportar **tipo (`porcentaje`/`fijo`) y monto**, no sólo porcentajes |
| S | **Interfaz del paso 1** | Datos del propietario generados por **JS**, con reglas anti-inyección |
| T | **Ventana de objeción en la UI** | Se fija por **botón + modal JS**, con respaldo si no hay JS |

---

## 1. Requisitos vigentes

1. Pueden publicar en representación: **corredor con suscripción vigente y plan habilitado**, **gerente** y **superadmin**.
2. El propietario **no** opera la plataforma.
3. **Paso 1** (`/prop/solicitar/`) pregunta *"¿Publicas tu propiedad o actúas como representante?"*. Si es representante, por **JS** aparecen los campos del propietario y el **mandato** se vuelve obligatorio.
4. **El mandato es obligatorio** y lo valida el gerente antes de asignar corredor.
5. La **OG** lleva cláusula de representación cuando aplica.
6. **El gerente aprueba la OG**, salvo el caso L (con marca).
7. **Aviso al propietario** con CCO a gerente y superadmin, y **advertencia al representante** antes de enviarlo.
8. El representante sube los documentos y completa los datos.
9. **Cupo mensual por plan.**
10. **No se publica antes de vencer la ventana de objeción** (1 a 7 días).
11. **Al subir la OG se capturan las condiciones económicas**, con **exigencia de trazabilidad diferenciada por rol**.
12. **El cierre económico acepta comisión por porcentaje o por monto fijo**, en ambas partes.

---

## 2. Estado actual y hallazgos

### 2.1 El flujo de cinco pasos, hoy

| Paso | Actor | Vista | Qué hace |
|---|---|---|---|
| 1 | Solicitante | `solicitar_publicacion` (1042) | Datos + fotos + comprobante. Crea `Propiedad(dueno=request.user)` |
| 2 | Gerente | `aprobar_pago_solicitud` (1249) | Aprueba pago, asigna responsable |
| 3 | Corredor | `subir_orden_gestion` (1433) | Sube la OG (sólo archivo) |
| 4a | Solicitante | `aceptar_orden_gestion` (1478) | Acepta → `og_aceptada` |
| 4b | Solicitante | `completar_datos_propiedad` (1520) | Datos, servicios, documentos, fotos |
| 5 | Corredor | `validar_solicitud` / `publicar_solicitud` | Valida y publica |

Estados reales: `pago_revision`, `pago_objetado`, `pago_aprobado`, `esperando_corredor`, `en_revision_corredor`, `og_pendiente`, `en_validacion`, `publicada`, `rechazada`, `cancelada`.

### 2.2 La fractura

`solicitud.usuario` es a la vez solicitante, dueño de la propiedad y quien acepta la OG (`solicitar_publicacion` 1085-1086, `aceptar_orden_gestion` 1481, `completar_datos_propiedad` 1523, `publicar_solicitud` 1675).

### 2.3 Los tres atascos de `detalle_solicitud.html`

La plantilla encadena bloques por actor:

```
 95:  {% if request.user == solicitud.corredor_asignado %}
224:  {% elif request.user == solicitud.usuario %}
301:  {% elif request.user.rol in 'gerente,superadmin' %}
380:  {% endif %}
```

**Atasco 1 — `og_pendiente`, representante que es también el corredor asignado.**
El bloque del corredor (166-168) muestra *"⏳ El usuario está revisando la OG"*. El botón de aceptar vive en el bloque de `usuario` (268), que no se renderiza. **Varado.**

**Atasco 2 — `og_aceptada` / `en_validacion`, mismo caso.**
El bloque del corredor (170-172) muestra *"⏳ El usuario está completando los datos"*. El botón "Completar datos" vive en el bloque de `usuario` (288 y 296). **Varado.**

**Atasco 3 — el gerente que se asigna a sí mismo.**
Gana el bloque de la línea 95 y su bloque de gerente (301) nunca se renderiza: no puede aprobar el pago, ni asignar corredor, ni aprobar la OG. **La decisión L es hoy inejecutable.**

**Además:** el bloque del gerente (301-378) no tiene ninguna rama para `og_pendiente`. La interfaz de aprobación de la OG **no existe**.

**La causa de los tres es la misma:** cada bloque está condicionado por **un solo atributo** (quién es) y no por **dos** (quién es *y* en qué etapa está). La sección 6 lo corrige.

### 2.4 Los campos `_og`: diseñados y nunca construidos

`a03Prop/models.py` (994-1022) define seis campos que ninguna vista escribe y ninguna plantilla lee:

| Campo | Tipo | `help_text` del autor |
|---|---|---|
| `precio_referencia_og` | Dec(15,2) | "Precio de venta o canon arriendo al momento de la OG" |
| `tipo_comision_vendedor_og` | Char, `porcentaje`/`fijo` | — |
| `valor_comision_vendedor_og` | Dec(10,2) | "% o monto fijo" |
| `tipo_comision_comprador_og` | Char, `porcentaje`/`fijo` | — |
| `valor_comision_comprador_og` | Dec(10,2) | "% o monto fijo" |
| `tasa_serca_og` | Dec(5,2) | **"Se pre-puebla desde el plan del corredor, editable"** |

Ese `help_text` prueba que la decisión O estaba diseñada y documentada, y nunca se construyó.

### 2.5 Hallazgos de infraestructura

**H1 — No hay notificación por correo en este flujo.** `_notificar()` (`a03Prop/views.py:877`) sólo crea la fila de `Communication`. `send_mail` aparece una vez en todo el proyecto, atado a la confirmación de cuenta.

**H2 — `Communication.recipient` es FK obligatoria a `User`.** Obstáculo que desaparece al dejar al propietario fuera.

**H3 — El cupo del plan no se aplica.** `max_propiedades_simultaneas` sólo se muestra (`a00seg/views.py:335`, `se_nuestro_agente.html:47`).

**H4 — `_get_plan_corredor()` está roto y la lógica está triplicada.**
`a03Prop/views.py:937-947` lee `corredor.plan.tasa_serca`, que no existe: siempre devuelve `("", 0)`. La lógica correcta está dos veces en `a00seg/views.py`:
```python
# comision_porcentaje es lo que RECIBE el corredor. SERCA cobra 100 - ese valor.
tasa_serca = 100.0 - float(suscripcion.plan.comision_porcentaje)
```
**`comision_porcentaje` es la parte del corredor**; SERCA cobra el complemento. Lo confirman el `help_text` del modelo (`a00seg/models.py:192`), el comentario de `views.py:1563` y `se_nuestro_agente.html:50`.

**H5 — Falta declarar un estado y sobra otro.**
`aceptar_orden_gestion` (1501) escribe `"og_aceptada"`, ausente de `ESTADO_CHOICES`: `paso_actual` devuelve 0 y la plantilla (46-63) pinta el paso 1 como activo. `gestion_view` (`a00seg/views.py:375`) filtra por `"datos_listos"`, inexistente.

**H6 — El radio de `dueno` es chico.** Cinco referencias en Python; unas trece en plantillas, casi todas comparaciones seguras con `None`. En SercaProp no hay herencia multi-tabla para arriendos.

**H7 — Notificaciones que dejarán de ser ciertas.** `subir_orden_gestion` (1467) pide al usuario *"acéptala"*; `aceptar_orden_gestion` (1507) emite como `USUARIO_BASE`.

**H8 — Los planes se administran por Django admin**, sin seed. `PlanSuscripcionAdmin` no define `fields`, así que los campos nuevos serán editables solos.

**H9 — El cierre económico sólo sabe sumar porcentajes.**
`a00seg/views.py:1553-1555`:
```python
com_vendedor  = precio_clp * pct_vendedor / 100
com_comprador = precio_clp * pct_comprador / 100
```
No hay rama de monto fijo, aunque el modelo de la OG sí distingue `porcentaje` de `fijo`. Y el formulario (`crear_cierre_economico.html:61-68`) sólo tiene campos de porcentaje.

**H10 — El bloque muerto de `planes.html` es más grande de lo que parece.**
Comenta de la línea 191 a la 286, y dentro quedan las líneas 203-283, que incluyen **todo el bucle que dibuja las tarjetas de planes de corredor**. Hoy `planes.html` **no muestra ninguna tarjeta de plan**; lo único vivo es el recuadro "mi suscripción" (288-301). Nomenclatura vieja: planes `'prime'`, comisiones 60/70%, 3/10 propiedades.

**H11 — No hay `Content-Security-Policy`.**
`settings.py` tiene `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER` y `CSRF_COOKIE_SECURE`, pero ninguna CSP. Relevante para la decisión S.

**H12 — La base local no es la de producción.** Los planes reales (**Barrio** y **Metrópoli**) viven en producción. Sus valores de cupo y comisión no están verificados aquí.
---

## 3. Alcance: qué se cae y qué queda

### Se descarta

| Se cae | Motivo |
|---|---|
| Cuenta de usuario para el propietario | No opera la plataforma |
| Capa de correo en todas las etapas | Sólo hay un aviso, con enlace para objetar |
| Estados y vistas de consentimiento y bloqueo del propietario | No hay máquina de consentimiento |
| Notificaciones al propietario por la bandeja interna | `Communication.recipient` exige `User` |
| Bloque muerto de `planes.html` (191-286) | Código de un esquema de planes anterior |
| La cadena `{% elif %}` por actor sin etapa | Causa de los tres atascos |

### Queda vigente

| Queda |
|---|
| Selector "propia o en representación" en el paso 1, con datos del propietario por JS |
| Mandato firmado obligatorio, validado por el gerente |
| Doble control del gerente: mandato y OG |
| Aviso al propietario con CCO a gerente y superadmin, ventana de 1 a 7 días |
| `dueno` nullable + `representante` + datos declarados |
| Cupo mensual calendario (Barrio 5 / Metrópoli 15) |
| **Captura de las condiciones económicas de la OG, con fiscalización por rol** |
| **Cierre económico con tipo y monto de comisión** |
| **Resolución de acciones del template por rol y etapa** |

**Cuatro de estos puntos no son de representación** y mejoran el flujo actual aunque la representación nunca se usara: la captura de comisiones de la OG, el cierre con tipo y monto, la resolución de acciones por rol y etapa, y la eliminación del bloque muerto. Eso ordena las fases de la sección 11.

---

## 4. Flujo definitivo

El representante **ocupa el casillero de `solicitud.usuario`**, que es quien crea la solicitud. Por eso la mayoría de los permisos actuales siguen funcionando sin tocarlos.

| Etapa | Actor | Acción | Estado |
|---|---|---|---|
| 1 | **Representante** (`usuario`) | Selector, datos del propietario, mandato, datos básicos, fotos, comprobante | `pago_revision` |
| 2 | **Gerente/Superadmin** | Aprueba el pago, **valida el mandato**, asigna responsable y **fija la ventana (modal)** | `en_revision_corredor` |
| — | **Sistema** | **Envía el aviso al propietario** con CCO, arranca `objecion_hasta` | — |
| 2b | **Corredor asignado** | Sube la OG **con sus condiciones económicas** | `og_pendiente` |
| 3 | **Gerente/Superadmin** | **Aprueba la OG**, con la trazabilidad de comisiones a la vista | `og_aceptada` |
| 4 | **Representante** (`usuario`) | Completa datos, servicios, documentos legales y fotos | `en_validacion` |
| 5 | **Corredor asignado** | Valida y publica, **sólo vencido `objecion_hasta`** y sin objeción | `publicada` |

### 4.1 Por qué la etapa 2 tiene dos actos del gerente

**La OG no existe cuando se aprueba el pago.** En la etapa 2 el gerente valida el comprobante y el mandato (la autorización del propietario); en la etapa 3 valida las condiciones comerciales. Dos objetos, dos momentos. Pueden ocurrir en la misma sesión de trabajo si el caso avanza rápido.

### 4.2 La etapa 2, en detalle

Con `tipo_publicante == representante`, la pantalla del gerente debe mostrar el comprobante, **los datos del propietario** (nombre y RUT), **el mandato descargable** con su tipo, el **cupo mensual disponible** del corredor a asignar, y el **modal de la ventana de objeción** (decisión T). Sin mandato cargado, **no puede aprobar**.

### 4.3 La etapa 2b: la OG deja de ser sólo un archivo, con fiscalización por rol

`subir_orden_gestion` (1444-1460) hoy sólo lee `request.FILES["orden_gestion"]` y `POST["docs_requeridos"]`. Pasa a capturar:

| Input | Campo destino | Prefijo |
|---|---|---|
| Precio de referencia (venta o canon) | `precio_referencia_og` | — |
| Tasa SERCA (%) | `tasa_serca_og` | Pre-poblado con `100 - plan.comision_porcentaje` |
| Tipo comisión vendedor (`porcentaje`/`fijo`) | `tipo_comision_vendedor_og` | — |
| Valor comisión vendedor | `valor_comision_vendedor_og` | — |
| Tipo comisión comprador (`porcentaje`/`fijo`) | `tipo_comision_comprador_og` | — |
| Valor comisión comprador | `valor_comision_comprador_og` | — |

**Decisión Q — la fiscalización es diferenciada por rol, y esto es lo nuevo.**

**Gerente y superadmin: sin fiscalización.** Es su negocio. Pueden poner la tasa y las comisiones que quieran. No hay topes, ni advertencias por superar el 100%, ni marca de desviación. Se registran los valores y nada más.

**Los demás roles (corredor / agente senior): con trazabilidad.** El corredor **no puede alterar en silencio** las condiciones del plan:

1. **Se guarda la tasa del plan junto a la que escribió el corredor.** Campo nuevo `tasa_serca_plan` en la solicitud. Sin esto, si el plan cambia después, no hay forma de reconstruir qué decía el plan al momento de la OG, y la auditoría se pierde.
2. **Rangos validados:** `tasa_serca_og` y los valores en `porcentaje` entre 0 y 100; los montos fijos, mayores o iguales a cero.
3. **Advertencia, no bloqueo,** si la suma de la tasa SERCA más las comisiones supera el 100%. Puede ser legítimo en un operación mixta, pero el gerente debe verlo.
4. **La desviación se muestra al gerente en la etapa 3**, que es quien fiscaliza: *"Tasa SERCA del plan: 75%. Tasa declarada en la OG: 60%. Desviación: −15 puntos."* El gerente decide si la aprueba.
5. **Queda registrado quién subió la OG y quién la aprobó** (`orden_gestion` se sube como `corredor_asignado`; `og_aceptada_por` guarda al aprobador).

El resultado es que un corredor puede pactar una tasa distinta a la del plan, pero **no puede hacerlo sin que quede escrito y sin que el gerente lo vea**. Eso es exactamente lo que pediste: libertad comercial con trazabilidad.

**Por qué esto importa en el cierre:** `CierreEconomico` (creado desde `a00seg/views.py:1566`) calcula hoy todo desde el plan y **nunca lee lo que dice la OG firmada** (ver H9 y 4.4).

### 4.4 El cierre económico con tipo y monto (decisión R)

Hoy el cálculo es sólo porcentual (`a00seg/views.py:1553-1555`) y el formulario sólo tiene dos campos de porcentaje. Con `tipo_comision_*_og` admitiendo `fijo`, eso queda incompleto.

**Nuevo contrato del formulario** (`crear_cierre_economico.html`, hoy líneas 57-71). Por cada parte, un tipo y un valor:

```
tipo_comision_vendedor    → porcentaje | fijo
valor_comision_vendedor
tipo_comision_comprador   → porcentaje | fijo
valor_comision_comprador
```

**Cálculo unificado:**

```python
def calcular_comision_clp(precio_clp, tipo, valor):
    """Comisión en CLP. `fijo` se interpreta en la misma moneda que el precio."""
    if tipo == "fijo":
        return float(valor or 0)
    return precio_clp * float(valor or 0) / 100
```

**Valores por defecto del formulario, en cascada:** primero lo que dice la OG firmada (`valor_comision_*_og` y `tipo_comision_*_og`), después el `CorredorProp` (`monto_comision_dueno` / `monto_comision_usu`) y por último el 2% actual. Así el cierre refleja **el contrato**, no el plan.

**Compatibilidad hacia atrás:** si la petición no trae `tipo_comision_vendedor`, el valor recibido en `pct_comision_vendedor` se trata como porcentaje. Un formulario viejo o un POST antiguo siguen funcionando igual que hoy.

**Y en `CierreEconomico` hay que dejar constancia del tipo**, porque hoy el registro guarda `pct_comision_vendedor` y con un monto fijo ese campo no significa nada. Hay que agregar (verificando la lista exacta de campos en la Fase 2):

```python
tipo_comision_vendedor  = models.CharField(max_length=20, choices=..., blank=True)
tipo_comision_comprador = models.CharField(max_length=20, choices=..., blank=True)
```

Cuando el tipo es `fijo`, el `pct_comision_*` se deja en `None` y el monto va en `comision_*_presupuestada_clp`, que ya existe.

**La única duda que queda abierta** y que conviene cerrar antes de la Fase 3: **¿en qué moneda se expresa una comisión fija?** Las dos lecturas razonables:

- **En la misma moneda que el precio.** Si la propiedad está en UF, "50" son 50 UF, y el cierre lo convierte con el `factor_uf_clp` que ya recibe. Es consistente con `precio_referencia_og`, que tampoco tiene campo de moneda y por tanto se entiende en la moneda de la propiedad.
- **Siempre en CLP.** "50.000" son 50.000 pesos, sin conversión, sin importar la moneda del precio.

**Recomendación: la misma moneda que el precio**, porque es lo que hace al sistema consistente consigo mismo, y porque el formulario del cierre ya recibe los factores de conversión. Si la preferencia es CLP, es un cambio de una línea en `calcular_comision_clp`.

**Y una advertencia:** como `precio_referencia_og` no tiene campo de moneda propio, en la interfaz conviene rotularlo explícitamente —*"Precio de referencia (en la moneda de la propiedad: UF)"*— para que nadie escriba pesos donde van UF.

---

## 5. Modelo de datos

### 5.1 `a03Prop/models.py` — `Propiedad`

```python
# CAMBIA: nullable y de CASCADE a SET_NULL.
dueno = models.ForeignKey(
    "a00seg.User", on_delete=models.SET_NULL, null=True, blank=True,
    related_name="propiedades", verbose_name="Dueño (si tiene cuenta)",
)

# NUEVO: quién opera el registro cuando el dueño no tiene cuenta
representante = models.ForeignKey(
    "a00seg.User", on_delete=models.SET_NULL, null=True, blank=True,
    related_name="propiedades_representadas", verbose_name="Representante",
)

# NUEVO: datos declarados del propietario
propietario_nombre   = models.CharField(max_length=255, blank=True)
propietario_dni      = models.CharField(max_length=20, blank=True)
propietario_email    = models.EmailField(blank=True)
propietario_celular  = models.CharField(max_length=20, blank=True)
en_representacion    = models.BooleanField(default=False)
```

**Invariante:** siempre debe existir `dueno` **o** (`en_representacion=True` con `representante`, `propietario_nombre` y `propietario_dni`). Validar en `Propiedad.clean()` y en la vista del paso 1.

```python
@property
def nombre_propietario_display(self):
    if self.dueno:
        return self.dueno.get_full_name() or self.dueno.email
    return self.propietario_nombre or "Propietario no informado"
```

### 5.2 `a03Prop/models.py` — `SolicitudPublicacion`

```python
class TipoPublicante(models.TextChoices):
    PROPIETARIO   = "propietario",   "El propio propietario"
    REPRESENTANTE = "representante", "Representante del propietario"

class TipoMandato(models.TextChoices):
    VERBAL   = "verbal",   "Verbal"
    ESCRITO  = "escrito",  "Escrito simple firmado"
    NOTARIAL = "notarial", "Notarial / poder amplio"

tipo_publicante = models.CharField(max_length=20, choices=TipoPublicante.choices, default="propietario")

# mandato
tipo_mandato         = models.CharField(max_length=20, choices=TipoMandato.choices, blank=True)
mandato_archivo      = models.FileField(upload_to="mandatos/", blank=True, null=True)
mandato_validado_por = models.ForeignKey("a00seg.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="mandatos_validados")
mandato_validado_at  = models.DateTimeField(null=True, blank=True)

# auditoría de quién aprobó la OG
og_aceptada_por = models.ForeignKey("a00seg.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="ogs_aprobadas")

# aviso y objeción
aviso_enviado_at    = models.DateTimeField(null=True, blank=True)
aviso_email_destino = models.EmailField(blank=True)
aviso_token         = models.CharField(max_length=64, blank=True)
aviso_abierto_at    = models.DateTimeField(null=True, blank=True)
objecion_hasta      = models.DateTimeField(null=True, blank=True)   # lo fija el gerente
objecion_dias       = models.PositiveSmallIntegerField(default=1)   # 1 a 7
objecion_at         = models.DateTimeField(null=True, blank=True)
objecion_motivo     = models.TextField(blank=True)
objetada            = models.BooleanField(default=False)

# NUEVO (decisión Q): la tasa del plan al momento de la OG, para auditoría
tasa_serca_plan = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
```

Declarar además los dos estados que hoy se usan y no están en `ESTADO_CHOICES`:

```python
("og_aceptada", "Orden de Gestión aprobada"),
("objetada",    "Objetada por el propietario"),
```

> **Los seis campos `_og` no se tocan.** Ya existen con el tipo y las `choices` correctas (2.4). Lo único que falta es escribirlos y leerlos.

### 5.3 `a00seg/models.py` — `PlanSuscripcion`

```python
permite_representacion = models.BooleanField(
    default=False, verbose_name="Permite publicar en representación"
)
max_publicaciones_mensual = models.PositiveSmallIntegerField(
    default=5, verbose_name="Máx. publicaciones por mes calendario"
)
```

- **Cambiar el `default=60.00` de `comision_porcentaje`**, herencia del esquema de 60/70%. Un default de un plan que ya no existe es una trampa para el próximo que cree un plan en el admin.
- **`max_propiedades_simultaneas` no se toca.** Sigue significando cartera simultánea.

### 5.4 `a00seg/models.py` — `CierreEconomico`

Agregar `tipo_comision_vendedor` y `tipo_comision_comprador` (sección 4.4) para que el registro sea autoexplicativo cuando la comisión es un monto fijo.

---

## 6. Resolución de acciones por rol y etapa

### 6.1 El diagnóstico, en una frase

Cada bloque de `detalle_solicitud.html` está condicionado por **un solo atributo** —quién es— y no por **dos**: quién es *y* en qué etapa está. De ahí salen los tres atascos de la sección 2.3.

### 6.2 Implementación recomendada: el modelo resuelve las acciones

En vez de llenar la plantilla de condiciones compuestas, la solicitud calcula qué puede hacer el usuario. Es la misma lógica —rol y etapa— pero en Python, donde se puede probar con tests.

```python
# a03Prop/models.py — dentro de SolicitudPublicacion

def acciones_de(self, user):
    """Acciones que `user` puede ejecutar en el estado actual.

    Es la única fuente de verdad de la máquina de estados para la interfaz.
    """
    if not user or not user.is_authenticated:
        return set()

    acciones = set()
    es_gerente = user.rol in ("gerente", "superadmin")
    es_responsable = user == self.corredor_asignado
    es_solicitante = user == self.usuario

    if es_gerente:
        if self.estado in ("pago_revision", "pago_objetado"):
            acciones.add("aprobar_pago")
        if self.estado in ("pago_aprobado", "esperando_corredor"):
            acciones.add("asignar_corredor")
        if self.estado == "og_pendiente":
            acciones.add("aprobar_og")

    if es_responsable:
        if self.estado == "en_revision_corredor":
            acciones.add("subir_og")
        if self.estado == "en_validacion":
            acciones.add("validar_publicar")

    if es_solicitante:
        if self.estado == "og_aceptada":
            acciones.add("completar_datos")
        if self.estado == "en_validacion":
            acciones.add("editar_datos")

    return acciones
```

Y la plantilla pasa a ser trivialmente correcta, con bloques independientes que pueden coexistir:

```django
{% with acciones=solicitud.acciones_de request.user %}

  {# Estado y trazabilidad, visible para cualquiera que vea la solicitud #}
  {% include "includes/solicitud_estado.html" %}

  {% if 'subir_og' in acciones %}
      {% include "includes/form_orden_gestion.html" %}
  {% endif %}

  {% if 'aprobar_pago' in acciones %}
      {% include "includes/accion_aprobar_pago.html" %}
  {% endif %}

  {% if 'asignar_corredor' in acciones %}
      {% include "includes/accion_asignar_corredor.html" %}
  {% endif %}

  {% if 'aprobar_og' in acciones %}
      {% include "includes/accion_aprobar_og.html" %}
  {% endif %}

  {% if 'completar_datos' in acciones %}
      <a href="{% url 'completar_datos_propiedad' solicitud.id %}" class="btn btn-primary btn-block">
          ✏️ Completar datos de la propiedad
      </a>
  {% endif %}

  {% if 'editar_datos' in acciones %}
      <a href="{% url 'completar_datos_propiedad' solicitud.id %}" class="btn btn-ghost btn-sm">
          ✏️ Editar datos
      </a>
  {% endif %}

  {% if 'validar_publicar' in acciones %}
      {% include "includes/accion_validar_publicar.html" %}
  {% endif %}

  {% if not acciones %}
      <div class="alert-modern alert-info-modern">No hay acciones pendientes para ti en esta etapa.</div>
  {% endif %}

{% endwith %}
```

**Por qué esta forma y no la cadena:**

- **Los tres atascos desaparecen por construcción.** Un usuario con dos roles obtiene la unión de sus acciones, no la primera que coincida.
- **Es testeable.** Un test recorre los diez estados contra los cuatro roles y verifica el conjunto. Eso es lo que impide que el defecto vuelva.
- **Django no tiene paréntesis en plantillas.** Un `{% if a and b or c %}` se evalúa con una precedencia que sorprende y no se puede agrupar. Cada condición compuesta en la plantilla es un riesgo latente; aquí sólo hay una comprobación de pertenencia.
- **Una sola fuente de verdad.** Hoy la lógica está repartida entre la vista, la plantilla y los permisos de cada vista. Añadir un rol o una etapa pasa a ser una línea en un solo lugar.

### 6.3 Verificación de que resuelve los tres atascos

Con `acciones_de` aplicado a los casos problemáticos:

| Caso | `acciones_de` devuelve | Antes |
|---|---|---|
| Representante = corredor, estado `og_pendiente` | `set()` → ve el mensaje de espera; **el gerente** ve `aprobar_og` | Atasco 1: nadie podía aceptar |
| Representante = corredor, estado `og_aceptada` | `{completar_datos}` | Atasco 2: el botón no se renderizaba |
| Representante = corredor, estado `en_validacion` | `{validar_publicar, editar_datos}` | Atasco 2: sólo uno de los dos |
| Gerente autoasignado, estado `pago_revision` | `{aprobar_pago}` | Atasco 3: no veía nada |
| Gerente autoasignado, estado `og_pendiente` | `{aprobar_og}` | Atasco 3: no podía aprobar la OG |

### 6.4 Si prefieres no tocar el modelo: la cadena con dos atributos

Es viable y funciona, siempre que **cada condición lleve rol y etapa juntos**:

```django
{% if request.user == solicitud.corredor_asignado and solicitud.estado == 'en_revision_corredor' %}
    … subir OG …
{% elif request.user.rol in 'gerente,superadmin' and solicitud.estado == 'pago_revision' %}
    … aprobar pago …
{% elif request.user.rol in 'gerente,superadmin' and solicitud.estado == 'pago_objetado' %}
    … aprobar pago …
{% elif request.user.rol in 'gerente,superadmin' and solicitud.estado == 'pago_aprobado' %}
    … asignar corredor …
{% elif request.user.rol in 'gerente,superadmin' and solicitud.estado == 'esperando_corredor' %}
    … asignar corredor …
{% elif request.user.rol in 'gerente,superadmin' and solicitud.estado == 'og_pendiente' %}
    … aprobar OG …
{% elif request.user == solicitud.usuario and solicitud.estado == 'og_aceptada' %}
    … completar datos …
{% elif request.user == solicitud.corredor_asignado and solicitud.estado == 'en_validacion' %}
    … validar y publicar …
    {% if request.user == solicitud.usuario %}
        … más el enlace para editar datos, porque el mismo usuario cumple ambos roles …
    {% endif %}
{% else %}
    … sólo el estado …
{% endif %}
```

**Limitaciones que hay que asumir con esta forma:** `pago_revision` y `pago_objetado` no se pueden agrupar en una condición sin paréntesis, así que hay que duplicar ramas; y **sólo funciona si no aparece nunca una etapa en la que dos roles distintos actúen y el mismo usuario tenga ambos**, porque el `elif` muestra una sola. Hoy el único caso así es `en_validacion`, y se resuelve añadiendo el enlace de edición dentro de la rama. Si mañana se agrega otro, la plantilla se rompe en silencio.

### 6.5 El formulario de la OG con las condiciones económicas

Dentro de la acción `subir_og` (`includes/form_orden_gestion.html`), con la fiscalización por rol de 4.3:

```django
<form method="POST" action="{% url 'subir_orden_gestion' solicitud.id %}" enctype="multipart/form-data">
  {% csrf_token %}

  <div class="form-group">
    <label>Orden de Gestión (archivo) *</label>
    <input type="file" name="orden_gestion" accept="application/pdf,image/*" required>
  </div>

  {% if solicitud.tipo_publicante == 'representante' %}
    <label class="toggle-checkbox">
      <input type="checkbox" name="incluye_representacion" value="1" required>
      La OG incluye la cláusula de representación, con nombre y RUT del propietario
    </label>
  {% endif %}

  <div class="form-group">
    <label>Precio de referencia (en {{ solicitud.propiedad.get_tipo_moneda_display }}) *</label>
    <input type="number" name="precio_referencia_og" step="0.01" min="0" required
           value="{{ solicitud.precio_referencia_og|default_if_none:'' }}">
    <div class="form-hint">El precio de venta o canon de arriendo escrito en la OG.</div>
  </div>

  <div class="form-group">
    <label>Tasa SERCA (%) *</label>
    <input type="number" name="tasa_serca_og" step="0.01" min="0" max="100" required
           value="{{ solicitud.tasa_serca_og|default:tasa_serca_plan|default:'' }}">
    {% if tasa_serca_plan %}
      <div class="form-hint">Tasa del plan: {{ tasa_serca_plan }}%. Puedes pactar otra, pero quedará registrada y la verá el gerente.</div>
    {% endif %}
  </div>

  {# ── Comisión vendedor ── #}
  <div class="form-row">
    <div class="form-group">
      <label>Tipo comisión vendedor</label>
      <select name="tipo_comision_vendedor_og">
        <option value="porcentaje" {% if solicitud.tipo_comision_vendedor_og == 'porcentaje' %}selected{% endif %}>Porcentaje</option>
        <option value="fijo"       {% if solicitud.tipo_comision_vendedor_og == 'fijo' %}selected{% endif %}>Monto fijo</option>
      </select>
    </div>
    <div class="form-group">
      <label>Valor comisión vendedor</label>
      <input type="number" name="valor_comision_vendedor_og" step="0.01" min="0"
             value="{{ solicitud.valor_comision_vendedor_og|default_if_none:'' }}">
    </div>
  </div>

  {# ── Comisión comprador (idéntico) ── #}
  <div class="form-row">
    <div class="form-group">
      <label>Tipo comisión comprador</label>
      <select name="tipo_comision_comprador_og">
        <option value="porcentaje" {% if solicitud.tipo_comision_comprador_og == 'porcentaje' %}selected{% endif %}>Porcentaje</option>
        <option value="fijo"       {% if solicitud.tipo_comision_comprador_og == 'fijo' %}selected{% endif %}>Monto fijo</option>
      </select>
    </div>
    <div class="form-group">
      <label>Valor comisión comprador</label>
      <input type="number" name="valor_comision_comprador_og" step="0.01" min="0"
             value="{{ solicitud.valor_comision_comprador_og|default_if_none:'' }}">
    </div>
  </div>

  <div class="form-group">
    <label>Documentos que debe subir el solicitante</label>
    <input type="text" name="docs_requeridos" value="{{ solicitud.docs_requeridos }}">
  </div>

  <button type="submit" class="btn btn-primary">📤 Subir Orden de Gestión</button>
</form>
```

Y la **vista** aplica la fiscalización por rol (decisión Q): valida rangos siempre; si el usuario es corredor, además guarda `tasa_serca_plan` y calcula la desviación; si es gerente o superadmin, guarda los valores tal cual, sin topes ni marcas:

```python
es_gerente = request.user.rol in ("gerente", "superadmin")
plan_nombre, tasa_plan = _get_plan_corredor(solicitud.corredor_asignado)

if tasa_plan and not es_gerente:
    tasa_og = Decimal(request.POST["tasa_serca_og"])
    if tasa_og != tasa_plan:
        # queda registrada; el gerente la verá al aprobar (etapa 3)
        solicitud.tasa_serca_plan = tasa_plan
        if tasa_og + Decimal(request.POST["valor_comision_vendedor_og"] or 0) > 100:
            messages.warning(request, "La suma de la tasa SERCA y la comisión del vendedor supera el 100%. El gerente deberá aprobarlo.")
```

### 6.6 La rama nueva: aprobar la OG

`includes/accion_aprobar_og.html` — la interfaz que hoy no existe. Es la que hace ejecutable la decisión L:

```django
<div class="card-modern">
  <div class="card-modern-body">
    <div class="card-modern-title">📋 Aprobar la Orden de Gestión</div>

    <p><strong>Subida por:</strong> {{ solicitud.corredor_asignado.get_full_name|default:solicitud.corredor_asignado.email }}</p>
    <p><strong>Archivo:</strong> <a href="{{ solicitud.orden_gestion.url }}" target="_blank">Ver la OG</a></p>

    {% if solicitud.tipo_publicante == 'representante' %}
      <div class="alert-modern alert-warning-modern">
        Publicación <strong>en representación</strong> de
        {{ solicitud.propiedad.propietario_nombre }} ({{ solicitud.propiedad.propietario_dni }}).
        Mandato: {{ solicitud.get_tipo_mandato_display }}.
        <a href="{{ solicitud.mandato_archivo.url }}" target="_blank">Ver mandato</a>.
      </div>
    {% endif %}

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
      <span>Precio de referencia:</span><strong>{{ solicitud.precio_referencia_og }}</strong>
      <span>Tasa SERCA declarada:</span><strong>{{ solicitud.tasa_serca_og }}%</strong>
      <span>Comisión vendedor:</span><strong>{{ solicitud.valor_comision_vendedor_og }} ({{ solicitud.get_tipo_comision_vendedor_og_display }})</strong>
      <span>Comisión comprador:</span><strong>{{ solicitud.valor_comision_comprador_og }} ({{ solicitud.get_tipo_comision_comprador_og_display }})</strong>
    </div>

    {% if solicitud.tasa_serca_plan and solicitud.tasa_serca_plan != solicitud.tasa_serca_og %}
      <div class="alert-modern alert-warning-modern">
        ⚠️ Tasa SERCA del plan: <strong>{{ solicitud.tasa_serca_plan }}%</strong>.
        Declarada en la OG: <strong>{{ solicitud.tasa_serca_og }}%</strong>.
        Quien subió la OG fue {{ solicitud.corredor_asignado.get_full_name }}.
      </div>
    {% endif %}

    {% if solicitud.og_aceptada_por == solicitud.corredor_asignado %}
      <div class="alert-modern alert-info-modern">Aprobada por el propio responsable.</div>
    {% endif %}

    <form method="POST" action="{% url 'aceptar_orden_gestion' solicitud.id %}">
      {% csrf_token %}
      <label>
        <input type="checkbox" name="acepta" required>
        Apruebo la OG en nombre del propietario, con esta trazabilidad a la vista
      </label>
      <button type="submit" class="btn btn-success">✅ Aprobar la Orden de Gestión</button>
    </form>
  </div>
</div>
```

### 6.7 La ventana de objeción por modal (decisión T)

El gerente aprueba el pago con un botón que abre un modal, donde fija los días. **Con respaldo si no hay JS**, para que la aprobación no se bloquee:

```django
<form method="POST" action="{% url 'aprobar_pago_solicitud' solicitud.id %}" id="form-aprobar-pago">
  {% csrf_token %}
  <select name="corredor_id" required>…</select>

  {# El valor real que se envía. Visible si no hay JS. #}
  <div class="form-group" id="wrap-objecion-dias">
    <label for="objecion_dias">Días de plazo para que el propietario objete (1 a 7)</label>
    <input type="number" name="objecion_dias" id="objecion_dias" value="1" min="1" max="7" required>
  </div>

  <button type="button" class="btn btn-success" onclick="abrirModalVentana()">
    ✅ Aprobar pago y asignar responsable
  </button>
  <noscript>
    <button type="submit" class="btn btn-success">✅ Aprobar pago y asignar responsable</button>
  </noscript>
</form>

<div id="modal-ventana" hidden>
  <div class="modal-caja">
    <h3>Plazo de objeción del propietario</h3>
    <p>Se enviará el aviso al propietario ahora y no se podrá publicar hasta que venza el plazo.</p>
    <input type="number" id="modal-dias" value="1" min="1" max="7">
    <button type="button" onclick="confirmarVentana()">Confirmar y aprobar</button>
    <button type="button" onclick="cerrarModalVentana()">Cancelar</button>
  </div>
</div>

<script>
function abrirModalVentana() {
  const modal = document.getElementById('modal-ventana');
  document.getElementById('modal-dias').value =
    document.getElementById('objecion_dias').value || 1;
  modal.hidden = false;
}
function cerrarModalVentana() {
  document.getElementById('modal-ventana').hidden = true;
}
function confirmarVentana() {
  const dias = document.getElementById('modal-dias').value;
  document.getElementById('objecion_dias').value = dias;   // el input real del form
  document.getElementById('form-aprobar-pago').submit();
}
</script>
```

El modal **escribe en el input real del formulario**, no en un campo aparte, y el `<noscript>` deja el camino sin JS funcionando con el valor por defecto de 1 día.

### 6.8 Qué cambia en las vistas

De las once vistas del flujo, **sólo un permiso cambia de dueño**:

| Vista | Permiso | ¿Cambia? |
|---|---|---|
| `solicitar_publicacion` (1042) | crea con `usuario=request.user` | No. Se agregan datos, mandato, `dueno` y cupo |
| `detalle_solicitud` (1145) | `usuario` ∥ `corredor` ∥ gerente | No. Debe exponer `acciones_de` |
| `agregar_observacion` | `usuario` ∥ gerente ∥ corredor | No |
| `aprobar_pago_solicitud` (1249) | `rol in (gerente, superadmin)` | No. Se agrega mandato y ventana |
| `subir_orden_gestion` (1433) | `request.user == corredor_asignado` | No. Se agregan los `_og` |
| **`aceptar_orden_gestion` (1478)** | **`request.user == solicitud.usuario`** | **SÍ** → `rol in ("gerente","superadmin")`, guarda `og_aceptada_por` |
| `completar_datos_propiedad` (1520) | `request.user == solicitud.usuario` | No |
| `subir_fotos_propiedad` | `request.user == solicitud.usuario` | No |
| `validar_solicitud` (1604) | `request.user == corredor_asignado` | No |
| `publicar_solicitud` (1653) | `request.user == corredor_asignado` | No. Se agregan las guardas de `objetada` y ventana |
| `cancelar_solicitud` | `usuario` ∥ gerente | No |

Y en `aceptar_orden_gestion` hay que corregir lo que dice el hallazgo H7: el permiso de 1481 y el `source_type` de 1507 (`USUARIO_BASE` → `GERENTE`). El mensaje de `subir_orden_gestion` (1467) debe dejar de pedirle al usuario que acepte.

---

## 7. Cupos mensuales por plan

### 7.1 Regla

**Mes calendario.** Corredor con plan habilitado: **5** (Barrio) o **15** (Metrópoli). Gerente y superadmin: sin cupo.

Se cuentan las `SolicitudPublicacion` con `usuario=corredor` creadas en el mes en curso, **excluyendo** `rechazada` y `cancelada`. Una publicación que no llegó a existir no consume cupo.

```python
inicio_mes = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

usadas = SolicitudPublicacion.objects.filter(
    usuario=corredor,
    created_at__gte=inicio_mes,
).exclude(estado__in=["rechazada", "cancelada"]).count()
```

**Decisión I:** cuenta la producción total del corredor en el mes, propia o en representación. Para restringirlo sólo a representación, basta agregar `tipo_publicante="representante"`.

### 7.2 Dónde se aplica

En `solicitar_publicacion`, **antes de crear nada**, sólo con el selector en "representante":

1. `rol in ("gerente", "superadmin")` → pasa siempre.
2. `rol == "corredor"` → suscripción vigente (`activa` **y** `fecha_fin` futura) y `plan.permite_representacion`.
3. `rol == "corredor"` → `usadas < plan.max_publicaciones_mensual`.

El mensaje debe decir el número y el mes: *"Tu plan permite 5 publicaciones por mes y ya usaste 5. Podrás publicar nuevamente en octubre."*

**Refuerzo en la etapa 2:** entre el paso 1 y el 2 puede pasar tiempo y el corredor puede haberse quedado sin cupo con otra solicitud.

### 7.3 Dependencia: arreglar `_get_plan_corredor` primero

Tres puntos dependen de leer el plan bien, y hoy la función está rota (H4). El arreglo, alineado con las dos copias de `a00seg/views.py`:

```python
def _get_plan_corredor(corredor):
    """Nombre del plan y tasa SERCA del corredor.

    comision_porcentaje es lo que RECIBE el corredor; SERCA cobra el complemento.
    """
    suscripcion = getattr(corredor, "suscripcion", None)
    if not suscripcion or not suscripcion.plan:
        return "", Decimal("0")
    return suscripcion.plan.nombre, Decimal("100") - suscripcion.plan.comision_porcentaje
```

**Nota de diseño:** la lógica queda en tres lugares (esta función y las dos copias de `a00seg/views.py`). Conviene unificarla en un helper compartido que usen `crear_cierre_economico`, el pre-poblado y el formulario de la OG. Si no se unifica, volverán a divergir, que es exactamente lo que produjo H4.
---

## 8. Aviso al propietario y objeción

### 8.1 Cuándo se envía

**En la etapa 2, cuando el gerente aprueba el pago y valida el mandato**, no al publicar. Así quedan tres etapas por delante (la OG, la aprobación y la carga de datos) para que el propietario pueda objetar antes de que nada salga al mercado.

### 8.2 La ventana

**Decisión G.** El gerente la fija en el modal de la etapa 2: **mínimo 1, máximo 7, por defecto 1**.

- `objecion_hasta = timezone.now() + timedelta(days=objecion_dias)`.
- `publicar_solicitud` rechaza publicar si `timezone.now() < objecion_hasta`, con la fecha en el mensaje: *"Esta publicación puede salir a partir del 6 de octubre, una vez vencido el plazo de objeción del propietario."*
- **El corredor ve el plazo** en el detalle. Sin esto, un rechazo sin contexto genera una llamada a soporte.
- Usar `timezone.now()`, no `datetime.now()`: el proyecto corre con `USE_TZ`.

### 8.3 Aviso al emisor (decisión N, primera mitad)

En el paso 1, junto al campo del correo del propietario, **antes** de enviar la solicitud, va este aviso visible y una casilla obligatoria:

> *"Se enviará un correo al propietario a la dirección que indiques, informándole de esta publicación y dándole la opción de objetarla. Se enviará copia oculta a la gerencia y a la superadministración de Serca Propiedades. Asegúrate de que el correo corresponde al propietario."*

Y una casilla: **"Declaro que el correo indicado pertenece al propietario y que cuento con su mandato para publicar."**

No impide un correo falso, pero convierte el acto en una declaración por escrito, hecha sabiendo que la gerencia y la superadministración reciben copia.

### 8.4 Envío con copia oculta (decisión N, segunda mitad)

- **Para:** el email declarado del propietario.
- **CCO:** los usuarios con `rol in ("gerente", "superadmin")` activos.
- **De:** `noreply@serca.online`, ya configurado.

**El backend ya lo soporta:** `a00seg/email_backends.py:64` hace `+ list(message.bcc or [])`.

> **Nota técnica:** `send_mail` de Django **no acepta `bcc`**. Hay que usar `EmailMultiAlternatives` (o `EmailMessage`).

### 8.5 Contenido y respuesta

El aviso identifica la propiedad (tipo, comuna, calle y número, sin datos de terceros), nombra al representante y a la correduría, declara que existe un mandato con su tipo, y trae un enlace público con token para **no autorizar esta publicación**, con campo de motivo.

**Al objetar:**
1. `objetada = True`, `objecion_at`, `objecion_motivo`.
2. Si la publicación ya existe, `PublicacionProp` pasa a `archivada` y la `Propiedad` sale de la vitrina.
3. Se notifica al gerente y al corredor con `_notificar`.

### 8.6 Implementación

`a03Prop/notificaciones.py::enviar_aviso_propietario(solicitud)`, con `EmailMultiAlternatives`, `bcc` desde `User.objects.filter(rol__in=("gerente","superadmin"), is_active=True)`, plantilla `templates/email/aviso_representacion.html` y envío en segundo plano (hay precedente en `a00seg/views.py::_enviar_email_en_segundo_plano`).

**Token:** `secrets.token_urlsafe(32)` en `aviso_token`. Un solo propósito: objetar o no objetar.

**Vista pública:** `path('representacion/<str:token>/', views.aviso_representacion, name='aviso_representacion')` en `a03Prop/urls.py`, sin `login_required`. **Registra `aviso_abierto_at` al abrirse**, que sirve incluso sin objeción: prueba que el propietario vio el aviso.

### 8.7 Límite honesto

El aviso va a un correo **que proporciona el representante**. Si pone el suyo, el propietario nunca se entera. **Mitiga, no garantiza.** Tres mitigaciones: la declaración jurada (8.3), la copia oculta (8.4) y el cotejo del correo contra el mandato en la etapa 2. Y queda `aviso_email_destino` registrado por si hay reclamo posterior.

---

## 9. El paso 1: selector, datos del propietario y seguridad

### 9.1 Dónde va

`solicitar_publicacion.html` tiene el formulario en la línea 14 (`id="solicitar-form"`) y un bloque `<script>` ya existente desde la 304. El selector va **al principio del formulario**, justo después del `{% csrf_token %}` de la línea 15, porque determina si aparece el bloque siguiente.

### 9.2 El HTML base

```django
<div class="form-group">
  <label for="id_tipo_publicante">¿Publicas tu propiedad o actúas como representante? *</label>
  <select name="tipo_publicante" id="id_tipo_publicante" required>
    <option value="propietario">Es mi propiedad</option>
    <option value="representante">Actúo como representante del propietario</option>
  </select>
</div>

{# Los campos del propietario los construye el JS dentro de este contenedor #}
<div id="bloque-representante" hidden></div>
```

El contenedor nace **vacío y oculto**: sin JS no hay campos, y el formulario sigue funcionando como hoy.

### 9.3 El JavaScript

```html
<script id="datos-representante-json" type="application/json">
  {"tiposMandato": [["escrito", "Escrito simple firmado"], ["notarial", "Notarial / poder amplio"]]}
</script>

<script>
(function () {
  "use strict";

  // Especificación estática de los campos. Sin datos de usuario aquí.
  var CAMPOS = [
    { n: "propietario_nombre",  e: "Nombre completo del propietario", t: "text",  req: true,  max: 255 },
    { n: "propietario_dni",     e: "RUT del propietario",             t: "text",  req: true,  max: 20  },
    { n: "propietario_email",   e: "Correo del propietario",          t: "email", req: true,  max: 254 },
    { n: "propietario_celular", e: "Teléfono del propietario",        t: "tel",   req: false, max: 20  },
    { n: "tipo_mandato",        e: "Tipo de mandato",                 t: "select",req: true  },
    { n: "mandato_archivo",     e: "Mandato firmado (PDF o imagen)",  t: "file",  req: true,  acepta: "application/pdf,image/*" }
  ];

  var contenedor = document.getElementById("bloque-representante");
  var selector   = document.getElementById("id_tipo_publicante");
  var construido = false;

  function crearCampo(spec) {
    var grupo = document.createElement("div");
    grupo.className = "form-group";

    var etiqueta = document.createElement("label");
    etiqueta.setAttribute("for", "id_" + spec.n);
    // textContent: el navegador lo trata como texto, nunca como marcado.
    etiqueta.textContent = spec.e + (spec.req ? " *" : "");
    grupo.appendChild(etiqueta);

    var campo;
    if (spec.t === "select") {
      campo = document.createElement("select");
      var tipos = JSON.parse(document.getElementById("datos-representante-json").textContent).tiposMandato;
      tipos.forEach(function (par) {
        var opcion = document.createElement("option");
        opcion.value = par[0];
        opcion.textContent = par[1];
        campo.appendChild(opcion);
      });
    } else {
      campo = document.createElement("input");
      campo.type = spec.t;
      if (spec.acepta) { campo.accept = spec.acepta; }
    }
    campo.id = "id_" + spec.n;
    campo.name = spec.n;
    campo.required = spec.req;
    if (spec.max) { campo.maxLength = spec.max; }
    grupo.appendChild(campo);
    return grupo;
  }

  function construir() {
    CAMPOS.forEach(function (spec) { contenedor.appendChild(crearCampo(spec)); });

    // Declaración jurada (decisión N). El texto es estático.
    var grupoJuramento = document.createElement("div");
    grupoJuramento.className = "form-group";
    var etiquetaJuramento = document.createElement("label");
    var casilla = document.createElement("input");
    casilla.type = "checkbox";
    casilla.name = "declara_mandato";
    casilla.value = "1";
    casilla.required = true;
    etiquetaJuramento.appendChild(casilla);
    etiquetaJuramento.appendChild(document.createTextNode(
      " Declaro que el correo indicado pertenece al propietario y que cuento con su mandato para publicar. " +
      "Se enviará copia oculta de ese aviso a la gerencia y a la superadministración de Serca Propiedades."
    ));
    grupoJuramento.appendChild(etiquetaJuramento);
    contenedor.appendChild(grupoJuramento);

    construido = true;
  }

  function alternar() {
    var esRepresentante = selector.value === "representante";
    if (esRepresentante && !construido) { construir(); }
    contenedor.hidden = !esRepresentante;

    // Los campos ocultos no deben quedar `required`: el navegador bloquearía el envío.
    contenedor.querySelectorAll("input, select").forEach(function (campo) {
      if (esRepresentante) {
        if (campo.type === "checkbox") { campo.required = true; }
        else {
          var spec = CAMPOS.filter(function (s) { return s.n === campo.name; })[0];
          campo.required = spec ? spec.req : false;
        }
      } else {
        campo.required = false;
        if (campo.type === "checkbox") { campo.checked = false; }
        else if (campo.type !== "file") { campo.value = ""; }
      }
    });
  }

  selector.addEventListener("change", alternar);
  alternar();   // estado inicial correcto si el navegador restaura el formulario
})();
</script>
```

### 9.4 Las reglas anti-inyección (decisión S)

La preocupación es correcta y estas son las reglas que hay que sostener en el código y en la revisión.

**En el JavaScript:**

1. **Construir con `createElement` y asignar texto con `textContent`.** Nunca `innerHTML`, `insertAdjacentHTML`, `outerHTML` ni `document.write`. El ejemplo de 9.3 no usa ninguno.
2. **Los datos del servidor no se concatenan en cadenas de marcado.** Si en el futuro hay que repoblar el formulario tras un error de validación, se hace con `campo.value = dato` —una asignación de propiedad, no marcado— y el dato se lee de un `data-` atributo con `dataset`, o de un `<script type="application/json">` parseado con `JSON.parse`. **Nunca** interpolando el valor dentro de un `<script>`.
3. **La especificación de los campos es estática.** Tipos, etiquetas y límites son literales del archivo. Ningún valor que venga del usuario decide qué se construye.

**En el servidor, que es donde de verdad está la frontera:**

4. **Nunca `|safe` ni `mark_safe`** sobre `propietario_nombre`, `propietario_dni`, `propietario_email`, `propietario_celular`, la dirección, ni `objecion_motivo`. El autoescaping de Django debe quedar activo — es la defensa real, no el JS.
5. **Validar en el servidor con un formulario de Django**, no con `request.POST.get` suelto: `EmailField` para el correo, `max_length` en todos los campos de texto, y el invariante de la sección 5.1 en `clean()`. La validación de JS es comodidad; la del servidor es la que cuenta, y es evitable por cualquiera que haga un POST directo.
6. **Rechazar los campos del propietario cuando el selector dice "propietario".** Un POST malicioso puede mandar los dos; la vista debe ignorar o rechazar los datos de representación si `tipo_publicante != "representante"`.
7. **`aviso_representacion` es la superficie de mayor riesgo**, porque es pública y sin login: muestra el nombre del propietario, el del representante, la dirección y el motivo de la objeción. Todo con autoescaping y sin excepciones.
8. **`objecion_motivo` se guarda y se muestra** al gerente y al corredor. Es texto libre de un tercero: mismo tratamiento, autoescaping siempre.

**Sobre la CSP:**

9. **No hay `Content-Security-Policy` hoy** (hallazgo H11). Añadirla es deseable, pero **no es gratis y conviene decirlo**: el proyecto usa `onclick=` en línea (por ejemplo `detalle_solicitud.html:344`) y bloques `<script>` en línea. Una política estricta con `script-src 'self'` **rompería la interfaz completa**. Los caminos razonables son empezar con `Content-Security-Policy-Report-Only` para medir el impacto, o desplegar una política permisiva que aún así bloquee lo peligroso (`object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'self'`) sin tocar los scripts en línea. Cualquiera de las dos es un cambio de `settings.py` más un middleware, y es **Fase 8**, no antes.

---

## 10. Cambios por archivo

### 10.1 Modelos

| Archivo | Cambio |
|---|---|
| `a03Prop/models.py` → `Propiedad` | `dueno` nullable y `SET_NULL`; nuevos `representante`, `propietario_nombre`, `propietario_dni`, `propietario_email`, `propietario_celular`, `en_representacion`; propiedad `nombre_propietario_display` |
| `a03Prop/models.py` → `SolicitudPublicacion` | `tipo_publicante`, `tipo_mandato`, `mandato_archivo`, `mandato_validado_por`, `mandato_validado_at`, `og_aceptada_por`, `aviso_enviado_at`, `aviso_email_destino`, `aviso_token`, `aviso_abierto_at`, `objecion_hasta`, `objecion_dias`, `objecion_at`, `objecion_motivo`, `objetada`, `tasa_serca_plan`; estados `og_aceptada` y `objetada`; **método `acciones_de`**. Los seis `_og` ya existen |
| `a00seg/models.py` → `PlanSuscripcion` | `permite_representacion`, `max_publicaciones_mensual`; cambiar el `default=60.00` de `comision_porcentaje` |
| `a00seg/models.py` → `CierreEconomico` | `tipo_comision_vendedor`, `tipo_comision_comprador` |

### 10.2 Vistas

| Archivo / vista | Cambio |
|---|---|
| `a03Prop/views.py` `_get_plan_corredor` (937) | Arreglar y **unificar las tres copias** en un helper compartido que devuelva nombre y tasa SERCA |
| `a03Prop/views.py` `solicitar_publicacion` (1042) | Selector, datos del propietario, mandato, validación de rol y cupo. `dueno` o `representante` + datos declarados |
| `a03Prop/views.py` `detalle_solicitud` (1145) | Exponer `acciones_de`, `tasa_serca_plan` y el plazo |
| `a03Prop/views.py` `aprobar_pago_solicitud` (1249) | Exigir mandato (con representación), registrar `mandato_validado_por/at`, revalidar cupo, **fijar `objecion_dias`/`objecion_hasta`**, **enviar el aviso con CCO** |
| `a03Prop/views.py` `subir_orden_gestion` (1433) | **Leer y guardar los seis `_og`**; guardar `tasa_serca_plan`; fiscalización por rol (Q); corregir el mensaje de 1467 |
| `a03Prop/views.py` `aceptar_orden_gestion` (1478) | Permiso a `rol in ("gerente","superadmin")`, guardar `og_aceptada_por`, `source_type` a `GERENTE` |
| `a03Prop/views.py` `publicar_solicitud` (1653) | Rechazar si `objetada` o si no venció `objecion_hasta` |
| `a03Prop/views.py` **nueva** `aviso_representacion` | Vista pública con token; registra `aviso_abierto_at` |
| `a03Prop/notificaciones.py` **nuevo** | `enviar_aviso_propietario` con `EmailMultiAlternatives` y CCO |
| `a00seg/views.py` `crear_cierre_economico` (1500-1586) | `calcular_comision_clp` con tipo y monto; defaults en cascada desde los `_og`; compatibilidad con `pct_comision_*` |
| `a00seg/views.py` `editar_cierre_economico` (1638+) | Idem en el pre-poblado y al guardar |
| `a00seg/views.py` `gestion_view` (375) | Quitar `"datos_listos"` |
| `a00seg/views.py` `perfil_view` (335) | Consumo del mes contra el cupo |
| `a00seg/views.py` `mis_propiedades` (345, 429) | `filter(Q(dueno=user) | Q(representante=user))` |

### 10.3 Plantillas

| Plantilla | Cambio |
|---|---|
| **`detalle_solicitud.html`** | Sustituir la cadena `{% elif %}` por los bloques de `acciones_de` (6.2) o por la cadena con rol y etapa (6.4). Bloque de estado común. **Nuevo** bloque de aprobación de la OG. Modal de la ventana y su `<noscript>` |
| **Nuevo** `includes/form_orden_gestion.html` | Formulario de la OG con los seis `_og` (6.5) |
| **Nuevo** `includes/accion_aprobar_og.html` | La rama de aprobación de la OG (6.6) |
| **Nuevos** `includes/accion_aprobar_pago.html`, `accion_asignar_corredor.html`, `accion_validar_publicar.html`, `solicitud_estado.html` | Extraer lo que hoy está embebido en la cadena |
| `solicitar_publicacion.html` | Selector, contenedor del propietario y **el JS de 9.3** |
| `crear_cierre_economico.html` | Línea 108: `{{ propiedad.dueno.get_full_name|default:propiedad.dueno.email }}` **rompe con `None`** → `{{ propiedad.nombre_propietario_display }}`. Y el bloque de comisiones (57-71) pasa a tipo + valor |
| `planes.html` | **Eliminar las líneas 191-286.** Ver 12.3 antes de borrar: dentro están las tarjetas de planes |
| `gestion_unificada.html` | Badge "En representación" y nombre del propietario declarado |
| `perfil.html` | Consumo del mes contra el cupo |
| **Nuevas** `aviso_representacion.html` y `email/aviso_representacion.html` | Página pública de objeción y correo al propietario |

### 10.4 Rutas, admin y datos

| Archivo | Cambio |
|---|---|
| `a03Prop/urls.py` | Ruta pública `representacion/<token>/` |
| `a00seg/admin.py` (93-96) | Agregar los campos nuevos a `list_display` de `PlanSuscripcionAdmin` |
| Biblioteca documental (`DocumentoGestion`) | Publicar la **plantilla de OG con cláusula de representación** y la de mandato. Cero código |
| Base de producción | **Verificar** cupo y comisión reales de Barrio y Metrópoli |

---

## 11. Fases

Las fases 3 y 4 **no tienen nada que ver con la representación**: cierran dos huecos del flujo actual. Van antes de tocar identidad y permisos.

**Fase 1 — Limpieza y correcciones.** No agrega funcionalidad.
`_get_plan_corredor` arreglado y unificado (H4); declarar `og_aceptada` y `objetada` (H5); quitar `"datos_listos"` (H5); `default` de `comision_porcentaje`; **decidir sobre el bloque de `planes.html`** (12.3). Verificable con la suite existente.

**Fase 2 — Modelo y migraciones.**
Campos de `Propiedad`, `SolicitudPublicacion`, `PlanSuscripcion` y `CierreEconomico`, más `acciones_de`. Nacen con valores por defecto que reproducen el flujo actual, así que **aplicar la migración no cambia producción**. Revisar en el mismo paso los ~18 lugares que leen `dueno` (12.2). **Escribir los tests de `acciones_de` aquí**: recorren los diez estados contra los cuatro roles y son la red que protege la Fase 4.

**Fase 3 — Condiciones económicas de la OG y cierre con tipo y monto (decisiones O, Q y R).**
Inputs `_og`, pre-poblado de la tasa, fiscalización por rol, `tasa_serca_plan`, `calcular_comision_clp`, el formulario del cierre con tipo + valor y los defaults en cascada. **Aplica igual al flujo actual.** Cierra el hueco por el que el cierre económico hoy ignora el contrato firmado.

**Fase 4 — Resolución de acciones por rol y etapa.**
Los bloques de `acciones_de` en `detalle_solicitud.html`, la extracción de los `includes`, **la rama nueva de aprobación de la OG**, y el cambio de permiso de `aceptar_orden_gestion` con su auditoría y sus notificaciones corregidas (H7). **Cierra los tres atascos y mejora también el flujo actual.** Es la fase con más riesgo de regresión visual: probar cada rol contra cada estado, con los tests de la Fase 2 como respaldo.

**Fase 5 — Representación en el paso 1.**
Selector, JS de los datos del propietario con las reglas de 9.4, mandato, declaración jurada, validación de rol y de cupo mensual.

**Fase 6 — Etapas 2 y 3 con representación.**
Validación del mandato y del cupo al aprobar el pago, **modal de la ventana**, aprobación de la OG por el gerente con la trazabilidad de comisiones a la vista, y la marca de auditoría de la decisión L.

**Fase 7 — Aviso, CCO y objeción.**
`enviar_aviso_propietario`, plantilla de correo, CCO a gerente y superadmin, token, vista pública con `aviso_abierto_at`, retiro de la publicación al objetar, y la guarda de la ventana en `publicar_solicitud`.

**Fase 8 — Listados, badges, cupo visible, admin y CSP.**
Badge "En representación", nombre del propietario en las listas, arreglo del `None` en `crear_cierre_economico.html`, consumo del mes en `perfil.html`, `list_display` del admin, y la CSP en modo `Report-Only`.

---

## 12. Riesgos residuales y deudas

### 12.1 El aviso depende de un dato que entrega el representante
Cubierto en 8.7. Tres mitigaciones; ninguna garantiza, todas encarecen el abuso.

### 12.2 `dueno` nullable
El radio es chico (H6), pero revisar antes de la migración: `a00seg/views.py:345`, `:395`, `:425`, `:429`; `crear_cierre_economico.html:108` (**rompe con `None`**); `detalle_propiedad.html:207, 242, 352, 363, 659, 664`; `gestion_unificada.html:81-82`; `includes/arriendo_flow_block.html:148, 286`.
Las comparaciones `user == p.dueno` son seguras con `None`; los displays no.
Cambiar `CASCADE` a `SET_NULL` es además una corrección por sí misma: hoy borrar un usuario borra sus propiedades, sus fotos, sus visitas y sus procesos.

### 12.3 Borrar el bloque de `planes.html` tiene una consecuencia
Ese bloque comentado **contiene el bucle que dibuja las tarjetas de planes de corredor** (203-283). Borrarlo deja esa sección sin tarjetas. Hay que decidir antes de la Fase 1:

- **Si quieres las tarjetas**, no basta borrar: hay que **reescribir la sección** con el esquema actual (`{{ plan.nombre }}`, `{{ plan.precio }}`, `{{ plan.max_propiedades_simultaneas }}`, `{{ plan.comision_porcentaje }}`), sin ninguna comparación contra `'prime'` y sin números hardcodeados.
- **Si no las quieres** porque `se_nuestro_agente.html` ya cumple esa función, se borra el bloque y se deja un comentario breve indicando por qué.

En cualquiera de los dos casos, la regla es no dejar comparaciones contra nombres de plan en la plantilla.

### 12.4 La autoaprobación del gerente está permitida (decisión L)
No se bloquea. Lo que hay que saber **no es una cuestión de honestidad sino de trazabilidad**: con la decisión O, la OG lleva las condiciones económicas, y un gerente que se asigna a sí mismo y aprueba su propia OG **fija y aprueba su propia remuneración**. La decisión Q lo exceptúa explícitamente de fiscalización, así que es coherente; lo que faltaba era que quedara a la vista.

Tres medidas, ninguna bloquea: **marca de auditoría** cuando `og_aceptada_por == corredor_asignado` (ya en 6.6), la **copia oculta** que da un segundo par de ojos en cada representación, y una **advertencia en la UI** al asignarse a sí mismo, para que sea una decisión consciente.

Si alguna vez se quisiera cerrar: una línea en `aceptar_orden_gestion` —no puede aprobar quien es `corredor_asignado`—. Queda documentada como opción, no aplicada.

### 12.5 Lógica de comisiones en tres lugares
`_get_plan_corredor` más las dos copias de `a00seg/views.py`. La Fase 1 las unifica. Si no se hace, volverán a divergir, que es exactamente lo que produjo H4.

### 12.6 El mandato firmado no es verificable por el sistema
Se sube un archivo y la plataforma no puede validar la firma ni la identidad del firmante. El control real es el gerente leyéndolo en la etapa 2. **Conviene que la gerencia lo sepa y no asuma lo contrario.**

### 12.7 Históricos de `CierreEconomico` con `tasa_serca = 0`
Guardados con el bug H4. **Decisión K:** se corrigen sólo hacia adelante; los antiguos quedan con la tasa en cero y así deben leerse.

### 12.8 La base local no es la de producción
Los planes reales (**Barrio** y **Metrópoli**) viven en producción. **Antes de la Fase 5 hay que leer sus valores** de cupo y comisión, tanto para no hardcodear nada como para confirmar que las páginas los muestran bien.

---

## 13. Estado de las decisiones

### Cerradas

Las veinte decisiones de la sección 0: **A a T**. Las cuatro últimas incorporan tu revisión final: fiscalización de comisiones diferenciada por rol (Q), cierre económico con tipo y monto (R), datos del propietario por JS con reglas anti-inyección (S), y ventana de objeción por botón y modal (T).

### Una sola pregunta abierta

**¿En qué moneda se expresa una comisión de tipo `fijo`?** En la misma moneda que el precio (si la propiedad está en UF, "50" son 50 UF, convertidas con el factor que el cierre ya recibe) o siempre en CLP.

Recomendación: **la misma moneda que el precio**, por consistencia con `precio_referencia_og`, que tampoco tiene campo de moneda. Si prefieres CLP, es una línea en `calcular_comision_clp`. Se puede cerrar durante la Fase 3.

### Todo lo demás son verificaciones, no decisiones

1. **Leer de producción** los valores de Barrio y Metrópoli (12.8).
2. **Decidir el destino de las tarjetas de `planes.html`** (12.3): reescribirlas o eliminarlas.

### Verificación previa a implementar

Los números de línea corresponden a la **revisión del 30-09-2026**. Si `a03Prop/views.py`, `a03Prop/models.py`, `a00seg/views.py` o `templates/detalle_solicitud.html` cambiaron después, hay que refrescar las referencias. Los nombres de función y los hallazgos H1 a H12 no dependen de la línea.
