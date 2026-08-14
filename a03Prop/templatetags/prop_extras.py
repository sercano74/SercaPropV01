import re

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


# ------------------------------------------------------------------
# Cloudinary: URL optimizada para pantallas pequeñas
# ------------------------------------------------------------------
# django-cloudinary-storage entrega URLs del tipo:
#   https://res.cloudinary.com/<cloud>/image/upload/v<timestamp>/<public_id>
# Sin transformaciones, el navegador descarga la imagen original completa
# (a veces 4K) y la encoge con CSS — pesada y borrosa en móvil.
#
# Este filtro inyecta transformaciones de Cloudinary delante de "image/upload":
#   w_800  : redimensiona a 800px (suficiente para tarjetas y retina 2x en móvil)
#   q_auto : calidad automática (webp/avif si el navegador lo soporta)
#   f_auto : formato automático
# El public_id puede incluir subcarpetas (p. ej. "propiedades/foto.jpg"),
# por eso capturamos el resto completo de la URL, no solo el último segmento.
_CDN_UPLOAD_RE = re.compile(r"(/image/upload/)(v\d+/)?([^?]+)$")


@register.filter
def cloud_thumb(url):
    """Devuelve una URL de Cloudinary optimizada (800px, q_auto, f_auto).

    Si la URL no es de Cloudinary (p. ej. media/ local, SVG estático o
    placeholder), devuelve la URL original sin cambios.
    """
    if not url:
        return ""
    url_str = str(url)
    if "res.cloudinary.com" not in url_str:
        return url_str
    match = _CDN_UPLOAD_RE.search(url_str)
    if not match:
        return url_str
    prefix, _version, public_id = match.groups()
    transform = "w_800,q_auto,f_auto/"
    return f"{url_str[:match.start()]}{prefix}{transform}{public_id}"
