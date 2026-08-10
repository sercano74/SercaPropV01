from django.conf import settings
from .models import Funcionario, User
from a01Com.models import Communication


def site_info(request):
    """Context processor que provee información global del sitio."""
    context = {
        "site_name": "Serca Propiedades",
        "site_slogan": "Corretaje de Propiedades",
        "funcionarios": Funcionario.objects.filter(is_active=True),
        "ga4_measurement_id": getattr(settings, "GA4_MEASUREMENT_ID", ""),
    }

    # CDC badge: mensajes no leídos para el usuario autenticado
    if request.user.is_authenticated:
        context["cdc_no_leidos"] = Communication.objects.filter(
            recipient=request.user, is_read=False, is_deleted=False
        ).count()
    else:
        context["cdc_no_leidos"] = 0

    return context
