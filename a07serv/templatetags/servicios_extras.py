from django import template
from django.utils import timezone
from ..models import ServicioPublicitario

register = template.Library()


@register.inclusion_tag("servicios/includes/bloque_home_servicios.html", takes_context=True)
def bloque_home_servicios(context):
    """Renderiza el bloque de servicios activos en la home."""
    servicios = ServicioPublicitario.objects.filter(
        estado="activo",
        fecha_expiracion__gte=timezone.now(),
    ).select_related("categoria", "publicante").order_by("-created_at")[:6]
    return {
        "servicios": servicios,
        "request": context["request"],
    }
