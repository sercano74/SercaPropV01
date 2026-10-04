"""Condiciones económicas de la Orden de Gestión.

Al subir la OG, quien la firma declara **en qué moneda y con qué tipo** cobra su
comisión, y deja registrada la tasa SERCA que aplica. Eso es lo que después
alimenta el cierre económico: hasta ahora el cierre calculaba todo desde el plan
y nunca leía el contrato firmado.

**Fiscalización diferenciada por rol (el punto central de este módulo):**

- **Gerente y superadministrador: sin fiscalización.** Es su negocio. Pueden
  pactar la tasa y las comisiones que quieran; se registran y nada más.
- **Los demás roles: con trazabilidad.** No hay topes de negocio, pero la tasa
  del plan se guarda junto a la declarada, y la desviación se le muestra al
  gerente, que es quien aprueba. El corredor conserva libertad comercial, pero
  no puede pactar distinto *en silencio*.

Las funciones de aquí son puras respecto de la base de datos: reciben el POST,
resuelven y devuelven datos, errores y advertencias. Escribir es tarea de la
vista, y eso es lo que las hace fáciles de probar.
"""

from . import comisiones

CAMPOS_MONEDA = ("PCL", "UF", "USD")


def _leer_decimal(post, campo):
    """``Decimal`` del POST, o ``None`` si viene vacío o inválido."""
    return comisiones._a_decimal(post.get(campo))


def _leer_texto(post, campo, por_defecto=""):
    valor = post.get(campo)
    if valor is None:
        return por_defecto
    return str(valor).strip()


def _leer_moneda(post, campo, por_defecto=comisiones.MONEDA_CLP):
    return comisiones.normalizar_moneda(_leer_texto(post, campo, por_defecto))


def _monedas_usadas(datos):
    """Monedas distintas de CLP que aparecen en las condiciones."""
    candidatas = {
        datos["moneda_referencia_og"],
        datos["moneda_comision_vendedor_og"],
        datos["moneda_comision_comprador_og"],
    }
    return {m for m in candidatas if m != comisiones.MONEDA_CLP}


def _validar_factores(datos, monedas):
    """Exige la tasa de cada moneda que se esté usando."""
    errores = []
    if comisiones.MONEDA_UF in monedas and datos["factor_uf_og"] is None:
        errores.append(
            "Indicaste montos en UF: falta el valor de la UF en pesos a la "
            "fecha de la Orden de Gestión."
        )
    if comisiones.MONEDA_USD in monedas and datos["factor_usd_og"] is None:
        errores.append(
            "Indicaste montos en dólares: falta el valor del dólar en pesos a "
            "la fecha de la Orden de Gestión."
        )
    if monedas and not datos["fecha_tipo_cambio_og"]:
        errores.append(
            "Indica la fecha del tipo de cambio usado en la Orden de Gestión."
        )
    return errores


def parsear_condiciones(post, *, user, tasa_plan=None):
    """Resuelve las condiciones económicas del formulario de la OG.

    Devuelve ``(datos, errores, advertencias)``.

    - ``datos``: valores listos para asignar a la solicitud.
    - ``errores``: impiden guardar la OG.
    - ``advertencias``: se muestran, no bloquean. Aquí vive la fiscalización.
    """
    datos = {
        "precio_referencia_og": _leer_decimal(post, "precio_referencia_og"),
        "moneda_referencia_og": _leer_moneda(post, "moneda_referencia_og"),
        "tasa_serca_og": _leer_decimal(post, "tasa_serca_og"),
        "tipo_comision_vendedor_og": _leer_texto(post, "tipo_comision_vendedor_og"),
        "valor_comision_vendedor_og": _leer_decimal(post, "valor_comision_vendedor_og"),
        "moneda_comision_vendedor_og": _leer_moneda(
            post, "moneda_comision_vendedor_og"
        ),
        "tipo_comision_comprador_og": _leer_texto(post, "tipo_comision_comprador_og"),
        "valor_comision_comprador_og": _leer_decimal(post, "valor_comision_comprador_og"),
        "moneda_comision_comprador_og": _leer_moneda(
            post, "moneda_comision_comprador_og"
        ),
        "factor_uf_og": _leer_decimal(post, "factor_uf_og"),
        "factor_usd_og": _leer_decimal(post, "factor_usd_og"),
        "fecha_tipo_cambio_og": _leer_texto(post, "fecha_tipo_cambio_og") or None,
    }

    datos["tipo_comision_vendedor_og"] = comisiones.normalizar_tipo(
        datos["tipo_comision_vendedor_og"]
    )
    datos["tipo_comision_comprador_og"] = comisiones.normalizar_tipo(
        datos["tipo_comision_comprador_og"]
    )

    errores = []
    advertencias = []

    if datos["precio_referencia_og"] is None:
        errores.append(
            "Falta el precio de referencia: el precio de venta o el canon de "
            "arriendo que dice la Orden de Gestión."
        )
    elif datos["precio_referencia_og"] < 0:
        errores.append("El precio de referencia no puede ser negativo.")

    if datos["tasa_serca_og"] is None:
        errores.append("Falta la tasa SERCA que aplica la Orden de Gestión.")

    errores.extend(
        comisiones.validar_rangos(
            tipo=datos["tipo_comision_vendedor_og"],
            valor=datos["valor_comision_vendedor_og"],
            tasa_serca=datos["tasa_serca_og"],
        )
    )
    errores.extend(
        comisiones.validar_rangos(
            tipo=datos["tipo_comision_comprador_og"],
            valor=datos["valor_comision_comprador_og"],
        )
    )

    if not errores:
        errores.extend(_validar_factores(datos, _monedas_usadas(datos)))

    # ------------------------------------------------------------------
    # Fiscalización: sólo para roles que no son la gerencia.
    # ------------------------------------------------------------------
    if comisiones.aplica_fiscalizacion(getattr(user, "rol", "")):
        datos["tasa_serca_plan"] = tasa_plan
        if (
            tasa_plan is not None
            and datos["tasa_serca_og"] is not None
            and datos["tasa_serca_og"] != tasa_plan
        ):
            desviacion = comisiones.desviacion_tasa(
                tasa_plan, datos["tasa_serca_og"]
            )
            advertencias.append(
                f"La tasa SERCA de tu plan es {tasa_plan}% y declaraste "
                f"{datos['tasa_serca_og']}% en la Orden de Gestión "
                f"({desviacion:+} puntos). Queda registrado y la gerencia lo "
                "verá al aprobar."
            )
        suma = _suma_tasa_y_porcentaje(datos)
        if suma is not None and suma > comisiones.CIEN:
            advertencias.append(
                "La tasa SERCA más la comisión del vendedor superan el 100%. "
                "Puede ser legítimo en una operación mixta, pero la gerencia "
                "tendrá que aprobarlo."
            )
    else:
        datos["tasa_serca_plan"] = None

    return datos, errores, advertencias


def _suma_tasa_y_porcentaje(datos):
    """Tasa SERCA + comisión del vendedor, si ambos son porcentajes."""
    if datos["tipo_comision_vendedor_og"] != comisiones.TIPO_PORCENTAJE:
        return None
    if datos["tasa_serca_og"] is None or datos["valor_comision_vendedor_og"] is None:
        return None
    return datos["tasa_serca_og"] + datos["valor_comision_vendedor_og"]


def resumen_fiscalizacion(solicitud, tasa_plan=None):
    """Datos para la pantalla de aprobación de la OG.

    Devuelve el desglose ya convertido a CLP y la desviación de la tasa, o
    ``None`` donde no haya dato. La plantilla no calcula nada.
    """
    plan = tasa_plan if tasa_plan is not None else solicitud.tasa_serca_plan
    return {
        "precio_referencia_clp": solicitud.precio_referencia_clp,
        "comision_vendedor_clp": solicitud.comision_vendedor_og_clp,
        "comision_comprador_clp": solicitud.comision_comprador_og_clp,
        "ingreso_bruto_clp": solicitud.ingreso_bruto_og_clp,
        "comision_serca_clp": solicitud.comision_serca_og_clp,
        "neto_corredor_clp": solicitud.neto_corredor_og_clp,
        "desviacion_tasa": comisiones.desviacion_tasa(plan, solicitud.tasa_serca_og),
        "tasa_plan": plan,
        "tiene_desviacion": bool(plan and solicitud.tasa_serca_og and plan != solicitud.tasa_serca_og),
    }


def mensaje_condiciones_guardadas(solicitud):
    """Resumen de una línea para el mensaje de éxito tras subir la OG."""
    bruto = solicitud.ingreso_bruto_og_clp
    if bruto is None:
        return ""
    return f"Comisión total declarada: {comisiones.formatear_clp(bruto)} CLP."


def valores_iniciales_para_cierre(propiedad):
    """Valores por defecto del cierre económico, en cascada.

    Orden de precedencia: **la OG firmada** (los campos ``_og``), después el
    ``CorredorProp`` y, si no hay ninguno de los dos, vacío. Así el cierre
    refleja el contrato y no el plan, que es justo el hueco que tenía antes:
    el cierre calculaba todo desde el plan e ignoraba lo que decía la OG.

    Devuelve los valores en crudo más los montos ya convertidos a CLP con la
    tasa de la OG. Los ``None`` significan "no hay dato", nunca cero.
    """
    datos = {
        "origen_comisiones": "",
        "tipo_comision_vendedor": "",
        "valor_comision_vendedor_origen": None,
        "moneda_comision_vendedor": comisiones.MONEDA_CLP,
        "comision_vendedor_clp": None,
        "tipo_comision_comprador": "",
        "valor_comision_comprador_origen": None,
        "moneda_comision_comprador": comisiones.MONEDA_CLP,
        "comision_comprador_clp": None,
        "precio_referencia": None,
        "moneda_referencia": getattr(propiedad, "tipo_moneda", comisiones.MONEDA_CLP),
        "factor_uf_og": None,
        "factor_usd_og": None,
        "tasa_serca": None,
    }

    solicitud = (
        propiedad.solicitudes
        .exclude(estado__in=["rechazada", "cancelada"])
        .order_by("-created_at")
        .first()
    )

    if solicitud and solicitud.tiene_condiciones_economicas:
        datos.update({
            "origen_comisiones": comisiones.ORIGEN_OG,
            "tipo_comision_vendedor": comisiones.normalizar_tipo(
                solicitud.tipo_comision_vendedor_og
            ),
            "valor_comision_vendedor_origen": solicitud.valor_comision_vendedor_og,
            "moneda_comision_vendedor": comisiones.normalizar_moneda(
                solicitud.moneda_comision_vendedor_og
            ),
            "comision_vendedor_clp": solicitud.comision_vendedor_og_clp,
            "tipo_comision_comprador": comisiones.normalizar_tipo(
                solicitud.tipo_comision_comprador_og
            ),
            "valor_comision_comprador_origen": solicitud.valor_comision_comprador_og,
            "moneda_comision_comprador": comisiones.normalizar_moneda(
                solicitud.moneda_comision_comprador_og
            ),
            "comision_comprador_clp": solicitud.comision_comprador_og_clp,
            "precio_referencia": solicitud.precio_referencia_og,
            "moneda_referencia": comisiones.normalizar_moneda(
                solicitud.moneda_referencia_og
            ),
            "factor_uf_og": solicitud.factor_uf_og,
            "factor_usd_og": solicitud.factor_usd_og,
            "tasa_serca": solicitud.tasa_serca_og,
        })
        return datos

    cp = propiedad.corredores.filter(estado="activa").first()
    if not cp:
        return datos

    datos.update({
        "origen_comisiones": comisiones.ORIGEN_CORREDOR_PROP,
        "tipo_comision_vendedor": comisiones.normalizar_tipo(cp.tipo_comision),
        "tipo_comision_comprador": comisiones.normalizar_tipo(cp.tipo_comision),
        "valor_comision_vendedor_origen": cp.monto_comision_dueno,
        "valor_comision_comprador_origen": cp.monto_comision_usu,
        "precio_referencia": propiedad.precio,
    })
    return datos


def calcular_comisiones_cierre(
    *,
    precio_clp,
    tipo_vendedor,
    valor_vendedor,
    moneda_vendedor=comisiones.MONEDA_CLP,
    tipo_comprador,
    valor_comprador,
    moneda_comprador=comisiones.MONEDA_CLP,
    factor_uf=None,
    factor_usd=None,
):
    """Comisiones del cierre en CLP. Acepta porcentaje o monto fijo."""
    vendedor = comisiones.calcular_comision_clp(
        base_clp=precio_clp, tipo=tipo_vendedor, valor=valor_vendedor,
        moneda=moneda_vendedor, factor_uf=factor_uf, factor_usd=factor_usd,
    )
    comprador = comisiones.calcular_comision_clp(
        base_clp=precio_clp, tipo=tipo_comprador, valor=valor_comprador,
        moneda=moneda_comprador, factor_uf=factor_uf, factor_usd=factor_usd,
    )
    return vendedor, comprador
