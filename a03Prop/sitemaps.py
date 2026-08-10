from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.db.models import Count
from django.utils import timezone

from .models import Propiedad, PublicacionProp
from a00seg.models import Comuna


def _dominio():
    """Dominio público canónico para SEO."""
    return getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")


def _urls_sitemap(sitemap_obj, dominio):
    """Genera las entradas <url> del sitemap con dominio absoluto canónico.

    Django 6.0 ya no resuelve el dominio a partir del Site automáticamente
    en todas las versiones, así que construimos las URLs completas a mano.
    """
    urls = []
    for item in sitemap_obj.items():
        location = sitemap_obj.location(item)
        if not location.startswith("http"):
            location = f"https://{dominio}{location}"
        entry = {"loc": location}
        lastmod = sitemap_obj.lastmod(item) if hasattr(sitemap_obj, "lastmod") else None
        if lastmod:
            entry["lastmod"] = lastmod.isoformat()
        changefreq = getattr(sitemap_obj, "changefreq", None)
        if changefreq:
            entry["changefreq"] = changefreq
        priority = getattr(sitemap_obj, "priority", None)
        if priority is not None:
            entry["priority"] = str(priority)
        urls.append(entry)
    return urls


class PropiedadSitemap(Sitemap):
    """Sitemap para las propiedades publicadas (solo indexables para SEO)."""
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Propiedad.objects.filter(
            estado="publicada",
            publicaciones__estado="publicada",
        ).distinct()

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        # Ruta relativa: la vista sitemap_xml construye la URL absoluta con el
        # dominio canónico propiedades.serca.online.
        return obj.get_absolute_url()


class StaticViewSitemap(Sitemap):
    """Sitemap para las páginas estáticas principales."""
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return ["home", "nosotros", "publica", "planes", "lista_servicios", "lista_casos_exito"]

    def location(self, item):
        return reverse(item)


class LandingSitemap(Sitemap):
    """Sitemap para las landing pages por comuna/categoría.

    Solo indexa combinaciones (comuna × acción × tipo) que tengan al menos
    una publicación activa, para no enviar landing vacías a Google.
    """
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        combos = (
            PublicacionProp.objects.filter(
                estado="publicada",
                expira_at__gte=timezone.now(),
                propiedad__comuna__isnull=False,
            )
            .values_list(
                "propiedad__comuna__slug",
                "propiedad__tipo_accion",
                "propiedad__tipo_prop",
            )
            .distinct()
        )
        return list(combos)

    def location(self, item):
        comuna_slug, accion, tipo_prop = item
        return reverse("landing_propiedades", kwargs={
            "accion": accion,
            "tipo_prop": tipo_prop,
            "comuna_slug": comuna_slug,
        })
