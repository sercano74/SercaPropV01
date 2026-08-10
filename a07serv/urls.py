from django.urls import path
from . import views

urlpatterns = [
    # Directorio público
    path('', views.lista_servicios, name='lista_servicios'),
    path('detalle/<int:servicio_id>/', views.detalle_servicio, name='detalle_servicio'),
    path('detalle/<int:servicio_id>/mensaje/', views.enviar_mensaje_servicio, name='enviar_mensaje_servicio'),
    path('detalle/<int:servicio_id>/mensaje/<int:mensaje_id>/responder/', views.responder_mensaje_servicio, name='responder_mensaje_servicio'),
    path('detalle/<int:servicio_id>/calificar/', views.calificar_servicio, name='calificar_servicio'),

    # Contratar (publicante)
    path('contratar/', views.contratar_servicio, name='contratar_servicio'),
    path('contratar/confirmar-pago/', views.confirmar_pago_servicio, name='confirmar_pago_servicio'),

    # Gestión del publicante
    path('mis-servicios/', views.gestion_mis_servicios, name='gestion_mis_servicios'),
    path('mis-servicios/<int:servicio_id>/imagen/', views.subir_imagen_servicio, name='subir_imagen_servicio'),
    path('mis-servicios/<int:servicio_id>/mensajes/', views.log_mensajes_servicio, name='log_mensajes_servicio'),

    # Casos de Éxito (público)
    path('casos-exito/', views.lista_casos_exito, name='lista_casos_exito'),
    path('casos-exito/<int:caso_id>/', views.detalle_caso_exito, name='detalle_caso_exito'),

    # Administración (gerente/superadmin)
    path('admin/servicios/', views.gestion_admin_servicios, name='gestion_admin_servicios'),
    path('admin/servicios/revision/<int:servicio_id>/', views.detalle_revision_servicio, name='detalle_revision_servicio'),
    path('admin/casos-exito/', views.gestion_casos_exito, name='gestion_casos_exito'),
    path('api/propiedad-para-caso/<int:prop_id>/', views.api_propiedad_para_caso, name='api_propiedad_para_caso'),
]
