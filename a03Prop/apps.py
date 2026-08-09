from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


def _configurar_site_canonico(sender, **kwargs):
    """
    Configura el dominio canónico del Site de django.contrib.sites.
    Se ejecuta tras cada migrate para que el sitemap apunte siempre
    a https://propiedades.serca.online (no al host interno de Railway).
    """
    try:
        from django.contrib.sites.models import Site

        dominio = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
        nombre = getattr(settings, "SITE_NAME", "Serca Propiedades")
        Site.objects.update_or_create(
            pk=1,
            defaults={"domain": dominio, "name": nombre},
        )
    except Exception:
        # El signal no debe romper migrate si la tabla no existe aún.
        pass


class A03PropConfig(AppConfig):
    name = 'a03Prop'
    verbose_name = 'Propiedades (SEO)'

    def ready(self):
        post_migrate.connect(_configurar_site_canonico, sender=self)
