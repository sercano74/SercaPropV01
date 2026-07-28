from django.urls import path, include
from django.views.generic.base import RedirectView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # Redirigir URLs legacy a allauth
    path('login/', RedirectView.as_view(url='/accounts/login/', permanent=True), name='login'),
    path('logout/', RedirectView.as_view(url='/accounts/logout/', permanent=True), name='logout'),
    path('registro/', RedirectView.as_view(url='/accounts/signup/', permanent=True), name='registro'),
    path('nosotros/', views.nosotros_view, name='nosotros'),
    path('publica/', views.publica_view, name='publica'),
    path('planes/', views.planes_view, name='planes'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('gestion/', views.gestion_view, name='gestion'),
    path('agenda/', views.agenda_view, name='agenda'),
    path('validar-corredores/', views.validar_corredores_view, name='validar_corredores'),
    path('crear-gerente/', views.crear_gerente_view, name='crear_gerente'),

    # Flujo postulación a corredor
    path('se-nuestro-agente/', views.se_nuestro_agente, name='se_nuestro_agente'),
    path('postular/<int:plan_id>/', views.postular_corredor, name='postular_corredor'),
    path('revisar-postulaciones/', views.revisar_postulaciones, name='revisar_postulaciones'),
    path('postulacion/<int:solicitud_id>/', views.detalle_postulacion, name='detalle_postulacion'),

    # Gestión secciones
    path('gestion/publicaciones/', views.gestion_mis_publicaciones, name='gestion_mis_publicaciones'),
    path('gestion/asignadas/', views.gestion_mis_asignadas, name='gestion_mis_asignadas'),
    path('gestion/favoritas/', views.gestion_favoritas, name='gestion_favoritas'),
    path('gestion/precios/', views.gestion_precios_publicacion, name='gestion_precios_publicacion'),
    path('gestion/servicios/', views.gestion_servicios, name='gestion_servicios'),

    # Confirmación de email
    path('confirmar-email/<uidb64>/<token>/', views.confirmar_email_view, name='confirmar_email'),
    path('reenviar-confirmacion/', views.reenviar_confirmacion_view, name='reenviar_confirmacion'),

    # Gestión de Ingresos / Cierre Económico
    path('gestion/ingresos/', views.gestion_ingresos_view, name='gestion_ingresos'),
    path('gestion/ingresos/crear/<int:prop_id>/', views.crear_cierre_economico, name='crear_cierre_economico'),
    path('gestion/ingresos/editar/<int:cierre_id>/', views.editar_cierre_economico, name='editar_cierre_economico'),
    path('gestion/ingresos/eliminar/<int:cierre_id>/', views.eliminar_cierre_economico, name='eliminar_cierre_economico'),
]
