import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Tags/atributos permitidos por el editor de texto enriquecido (WYSIWYG)
# para las descripciones de propiedades y servicios.
_RTF_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s", "strike",
    "ol", "ul", "li", "h2", "h3", "h4", "blockquote",
    "a", "code", "pre", "span",
]
_RTF_ATTRS = {
    "a": ["href", "target", "rel", "title"],
    "span": ["class"],
}
_RTF_PROTOCOLS = ["http", "https", "mailto", "tel", "whatsapp"]


@register.filter
def safe_rtf(value):
    """Sanitiza HTML generado por el editor WYSIWYG (Quill) antes de renderizarlo.

    Permite solo etiquetas de formato (negritas, listas, enlaces, etc.)
    y elimina scripts, iframes y estilos peligrosos.
    """
    if not value:
        return ""
    limpiado = bleach.clean(
        value,
        tags=_RTF_TAGS,
        attributes=_RTF_ATTRS,
        protocols=_RTF_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    # mark_safe evita que Django escape el HTML sanitizado en el template.
    return mark_safe(limpiado)


@register.filter
def get_item(dictionary, key):
    """Obtiene un item de un diccionario por su clave."""
    return dictionary.get(key)


@register.filter
def money(value, decimales=-1):
    """
    Formatea un número monetario en formato chileno:
    separador de miles con punto y decimal con coma.

    Ejemplos:
        450000   -> "450.000"
        3200.5   -> "3.200,50"
        1234.56  -> "1.234,56"

    Parámetro opcional ``decimales``:
        -1 (default): automático — 0 decimales si el valor es entero,
                      2 decimales si tiene parte fraccionaria.
        0            : siempre entero redondeado.
        N            : forzar N decimales.
    """
    if value is None or value == "":
        return ""
    try:
        n = float(value)
    except (ValueError, TypeError):
        return str(value)

    if decimales == -1:
        if abs(n - round(n)) > 1e-9:
            decimales = 2
        else:
            decimales = 0

    if decimales == 0:
        s = f"{round(n):,.0f}"
    else:
        s = f"{n:,.{int(decimales)}f}"

    # Invertir separadores: anglosajón (1,234.56) -> chileno (1.234,56)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")
