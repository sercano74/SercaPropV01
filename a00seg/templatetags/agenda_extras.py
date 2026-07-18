from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Acceso a diccionario con clave variable."""
    if isinstance(d, dict):
        return d.get(key)
    return None
