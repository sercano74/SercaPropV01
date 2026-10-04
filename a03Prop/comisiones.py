"""Comisiones de la Orden de Gestión: conversión a CLP y fiscalización.

Dos reglas gobiernan este módulo, y conviene tenerlas a la vista porque son la
diferencia entre un cierre económico que cuadra y uno que no:

1. **El precio se convierte con la tasa del día del cierre.** Es el valor
   efectivo del negocio, el que realmente se cerró.

2. **La comisión pactada en la Orden de Gestión se convierte con la tasa de la
   fecha de la OG.** Es un monto contractual: se acordó en UF o en dólares un
   día determinado, y el corredor tiene derecho a ese monto, no al que resulte
   si la UF se movió mientras el negocio se cerraba.

Todo lo que llega a ``CierreEconomico`` viene ya expresado en CLP, calculado
con estas funciones, para que el registro sea reproducible años después.

La fiscalización es diferenciada por rol: el gerente y el superadministrador
son dueños del negocio y pueden pactar la comisión que quieran; los demás roles
quedan sujetos a rangos y a que la desviación respecto del plan quede a la
vista del gerente.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEDA_CLP = "PCL"
MONEDA_UF = "UF"
MONEDA_USD = "USD"
MONEDAS_VALIDAS = (MONEDA_CLP, MONEDA_UF, MONEDA_USD)

TIPO_PORCENTAJE = "porcentaje"
TIPO_FIJO = "fijo"
TIPOS_COMISION_VALIDOS = (TIPO_PORCENTAJE, TIPO_FIJO)

# Roles que fijan sus propias condiciones sin fiscalización: es su negocio.
ROLES_SIN_FISCALIZACION = ("gerente", "superadmin")

ORIGEN_OG = "og"
ORIGEN_CORREDOR_PROP = "corredor_prop"
ORIGEN_MANUAL = "manual"

CENTAVO = Decimal("0.01")
CIEN = Decimal("100")
UNO = Decimal("1")


def _a_decimal(valor):
    """Convierte a ``Decimal`` sin reventar con basura del formulario."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None


def _redondear(valor):
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def normalizar_moneda(moneda):
    """Devuelve una de las monedas válidas. ``CLP`` se guarda como ``PCL``."""
    texto = (moneda or "").strip().upper()
    if texto in ("", "CLP"):
        return MONEDA_CLP
    return texto if texto in MONEDAS_VALIDAS else MONEDA_CLP


def normalizar_tipo(tipo):
    """``porcentaje`` o ``fijo``. Cualquier otra cosa se lee como porcentaje."""
    texto = (tipo or "").strip().lower()
    return texto if texto in TIPOS_COMISION_VALIDOS else TIPO_PORCENTAJE


def factor_para(moneda, factor_uf=None, factor_usd=None):
    """Factor de conversión a CLP, o ``None`` si falta la tasa necesaria."""
    moneda = normalizar_moneda(moneda)
    if moneda == MONEDA_CLP:
        return UNO
    if moneda == MONEDA_UF:
        return _a_decimal(factor_uf)
    if moneda == MONEDA_USD:
        return _a_decimal(factor_usd)
    return None


def convertir_a_clp(monto, moneda, factor_uf=None, factor_usd=None):
    """Convierte ``monto`` a CLP. Devuelve ``None`` si falta la tasa."""
    monto = _a_decimal(monto)
    if monto is None:
        return None
    factor = factor_para(moneda, factor_uf, factor_usd)
    if factor is None:
        return None
    return _redondear(monto * factor)


def calcular_comision_clp(
    *, base_clp, tipo, valor, moneda=MONEDA_CLP, factor_uf=None, factor_usd=None
):
    """Comisión en CLP.

    - ``porcentaje``: ``valor`` es un porcentaje de ``base_clp``.
    - ``fijo``: ``valor`` es un monto expresado en ``moneda``.

    Devuelve ``None`` cuando faltan datos para calcular (por ejemplo, un monto
    fijo en UF sin el valor de la UF).
    """
    valor = _a_decimal(valor)
    if valor is None:
        return None

    if normalizar_tipo(tipo) == TIPO_FIJO:
        return convertir_a_clp(valor, moneda, factor_uf, factor_usd)

    base_clp = _a_decimal(base_clp)
    if base_clp is None:
        return None
    return _redondear(base_clp * valor / CIEN)


def aplicar_tasa(base_clp, tasa_pct):
    """Aplica un porcentaje a una base en CLP. ``None`` si falta algún dato."""
    base_clp = _a_decimal(base_clp)
    tasa = _a_decimal(tasa_pct)
    if base_clp is None or tasa is None:
        return None
    return _redondear(base_clp * tasa / CIEN)


def aplica_fiscalizacion(rol):
    """``True`` si el rol queda sujeto a rangos y trazabilidad."""
    return rol not in ROLES_SIN_FISCALIZACION


def validar_rangos(*, tipo, valor, tasa_serca=None):
    """Errores de rango de una línea de comisión. Lista vacía si está bien.

    No juzga si la comisión es alta o baja: eso es negocio. Sólo impide
    valores que no tienen sentido aritmético (porcentajes fuera de 0-100 o
    montos negativos).
    """
    errores = []
    valor = _a_decimal(valor)

    if valor is not None and valor < 0:
        errores.append("El valor de la comisión no puede ser negativo.")
    elif (
        normalizar_tipo(tipo) == TIPO_PORCENTAJE
        and valor is not None
        and valor > CIEN
    ):
        errores.append("Una comisión expresada en porcentaje no puede superar el 100%.")

    tasa = _a_decimal(tasa_serca)
    if tasa is not None and (tasa < 0 or tasa > CIEN):
        errores.append("La tasa SERCA debe estar entre 0% y 100%.")

    return errores


def desviacion_tasa(tasa_plan, tasa_og):
    """Diferencia en puntos entre la tasa del plan y la declarada en la OG.

    Devuelve ``None`` si falta cualquiera de las dos: sin dato no hay
    desviación que mostrar, y **no** se debe inventar un cero.
    """
    plan = _a_decimal(tasa_plan)
    og = _a_decimal(tasa_og)
    if plan is None or og is None:
        return None
    return _redondear(og - plan)


def formatear_clp(monto):
    """Formato de pesos para mensajes. ``$1.234.567`` o ``-`` si no hay dato."""
    monto = _a_decimal(monto)
    if monto is None:
        return "-"
    return "${:,.0f}".format(monto).replace(",", ".")
