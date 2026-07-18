from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('a00seg.urls')),
    path('com/', include('a01Com.urls')),
    path('prop/', include('a03Prop.urls')),
    path('servicios/', include('a07serv.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
