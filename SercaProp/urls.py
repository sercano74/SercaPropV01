from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # django-allauth: login, registro, password, social
    path('', include('a00seg.urls')),
    path('com/', include('a01Com.urls')),
    path('prop/', include('a03Prop.urls')),
    path('servicios/', include('a07serv.urls')),
]

# Servir archivos media siempre (producción necesita esto para fotos de perfil, etc.)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
