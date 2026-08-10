from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from a03Prop.sitemaps import PropiedadSitemap, StaticViewSitemap, LandingSitemap, _urls_sitemap
from a01Com.views import robots_txt


def sitemap_xml(request):
    """Genera sitemap.xml con el dominio canónico propiedades.serca.online."""
    from xml.dom import minidom
    import xml.etree.ElementTree as ET

    dominio = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
    urls = _urls_sitemap(PropiedadSitemap(), dominio)
    urls += _urls_sitemap(StaticViewSitemap(), dominio)
    urls += _urls_sitemap(LandingSitemap(), dominio)

    root = ET.Element("urlset")
    root.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")
    root.set("xmlns:xhtml", "http://www.w3.org/1999/xhtml")

    for u in urls:
        url_el = ET.SubElement(root, "url")
        loc = ET.SubElement(url_el, "loc")
        loc.text = u["loc"]
        if u.get("lastmod"):
            lastmod = ET.SubElement(url_el, "lastmod")
            lastmod.text = u["lastmod"]
        if u.get("changefreq"):
            cf = ET.SubElement(url_el, "changefreq")
            cf.text = u["changefreq"]
        if u.get("priority"):
            pr = ET.SubElement(url_el, "priority")
            pr.text = u["priority"]

    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
    # Formato legible con indentación
    xml_pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")
    return HttpResponse(xml_pretty, content_type="application/xml")


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # django-allauth: login, registro, password, social
    path('', include('a00seg.urls')),
    path('com/', include('a01Com.urls')),
    path('prop/', include('a03Prop.urls')),
    path('servicios/', include('a07serv.urls')),

    # ===== SEO =====
    # Vista propia: fuerza el dominio canónico propiedades.serca.online en
    # todas las URLs del sitemap (independiente del host de la request).
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('robots.txt', robots_txt, name='robots_txt'),
]

# Servir archivos media siempre (producción necesita esto para fotos de perfil, etc.)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
