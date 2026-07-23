from django.urls import path
from . import views

urlpatterns = [
    path('detalle/<int:prop_id>/', views.detalle_propiedad, name='detalle_propiedad'),

    # ===== SOLICITUD DE VISITA =====
    path('api/agenda-disponible/<int:prop_id>/', views.agenda_disponible_api, name='agenda_disponible_api'),
    path('detalle/<int:prop_id>/solicitar-visita/', views.solicitar_visita, name='solicitar_visita'),
    path('visita/<int:visita_id>/subir-orden/', views.subir_orden_visita, name='subir_orden_visita'),
    path('visita/<int:visita_id>/subir-orden-firmada/', views.subir_orden_visita_firmada, name='subir_orden_visita_firmada'),
    path('visita/<int:visita_id>/aceptar-orden/', views.aceptar_orden_visita, name='aceptar_orden_visita'),
    path('visita/<int:visita_id>/gestionar/', views.gestionar_solicitud_visita, name='gestionar_solicitud_visita'),
    path('visita/<int:visita_id>/realizada/', views.marcar_visita_realizada, name='marcar_visita_realizada'),
    path('visita/<int:visita_id>/gestionar-arriendo/', views.gestionar_arriendo, name='gestionar_arriendo'),

    # ===== PROPUESTA DE COMPRA/ARRIENDO =====
    path('visita/<int:visita_id>/crear-propuesta/', views.crear_propuesta, name='crear_propuesta'),
    path('propuesta/<int:propuesta_id>/gestionar/', views.gestionar_propuesta, name='gestionar_propuesta'),

    # ===== PROCESO DE COMPRA-VENTA (FLUJO DOCUMENTAL) =====
    path('proceso/<int:proceso_id>/', views.detalle_proceso_compra, name='detalle_proceso_compra'),
    # Promesa de Compraventa
    path('proceso/<int:proceso_id>/subir-promesa/', views.subir_promesa_compraventa, name='subir_promesa_compraventa'),
    path('proceso/<int:proceso_id>/aceptar-documento/<str:etapa>/', views.aceptar_documento_proceso, name='aceptar_documento_proceso'),
    path('proceso/<int:proceso_id>/objetar-documento/<str:etapa>/', views.objetar_documento_proceso, name='objetar_documento_proceso'),
    path('proceso/<int:proceso_id>/observar/<str:etapa>/', views.agregar_observacion_proceso, name='agregar_observacion_proceso'),
    path('proceso/<int:proceso_id>/avanzar-instrucciones/', views.avanzar_a_instrucciones, name='avanzar_a_instrucciones'),
    # Instrucciones Notariales
    path('proceso/<int:proceso_id>/subir-instrucciones/', views.subir_instrucciones_notariales, name='subir_instrucciones_notariales'),
    # Contrato de Compraventa + Notaría
    path('proceso/<int:proceso_id>/subir-contrato/', views.subir_contrato_notaria, name='subir_contrato_notaria'),
    # Firma notarial
    path('proceso/<int:proceso_id>/firma-notarial/', views.marcar_firma_notarial, name='marcar_firma_notarial'),
    # Inscripción CBR
    path('proceso/<int:proceso_id>/inscripcion-cbr/', views.iniciar_inscripcion_cbr, name='iniciar_inscripcion_cbr'),
    # Reactivar competidores
    path('proceso/<int:proceso_id>/reactivar/', views.reactivar_competidores, name='reactivar_competidores'),
    # Declarar ronda no superada (corredor fuerza nueva versión)
    path('proceso/<int:proceso_id>/declarar-ronda-no-superada/<str:etapa>/', views.declarar_ronda_no_superada, name='declarar_ronda_no_superada'),

    path('asignar-corredor/<int:prop_id>/', views.asignar_corredor, name='asignar_corredor'),
    path('aprobar-publicacion/<int:pub_id>/', views.aprobar_publicacion, name='aprobar_publicacion'),
    path('rechazar-publicacion/<int:pub_id>/', views.rechazar_publicacion, name='rechazar_publicacion'),
    path('renovar/<int:pub_id>/', views.renovar_publicacion, name='renovar_publicacion'),
    path('archivar/<int:prop_id>/', views.archivar_propiedad, name='archivar_propiedad'),
    path('buscar/', views.buscar_propiedades_api, name='buscar_propiedades_api'),

    # ===== FLUJO SOLICITUD PUBLICACIÓN (5 PASOS) =====
    path('solicitar/', views.solicitar_publicacion, name='solicitar_publicacion'),
    path('solicitud/<int:solicitud_id>/', views.detalle_solicitud, name='detalle_solicitud'),
    path('solicitud/<int:solicitud_id>/observar/', views.agregar_observacion, name='agregar_observacion'),
    path('solicitud/<int:solicitud_id>/aprobar-pago/', views.aprobar_pago_solicitud, name='aprobar_pago_solicitud'),
    path('solicitud/<int:solicitud_id>/rechazar-pago/', views.rechazar_pago_solicitud, name='rechazar_pago_solicitud'),
    path('solicitud/<int:solicitud_id>/asignar-corredor/', views.asignar_corredor_solicitud, name='asignar_corredor_solicitud'),
    path('solicitud/<int:solicitud_id>/subir-og/', views.subir_orden_gestion, name='subir_orden_gestion'),
    path('solicitud/<int:solicitud_id>/aceptar-og/', views.aceptar_orden_gestion, name='aceptar_orden_gestion'),
    path('solicitud/<int:solicitud_id>/completar-datos/', views.completar_datos_propiedad, name='completar_datos_propiedad'),
    path('solicitud/<int:solicitud_id>/subir-fotos/', views.subir_fotos_propiedad, name='subir_fotos_propiedad'),
    path('solicitud/<int:solicitud_id>/validar/', views.validar_solicitud, name='validar_solicitud'),
    path('solicitud/<int:solicitud_id>/publicar/', views.publicar_solicitud, name='publicar_solicitud'),
    path('solicitud/<int:solicitud_id>/cancelar/', views.cancelar_solicitud, name='cancelar_solicitud'),

    # ===== EDICIÓN DE PROPIEDAD (datos, fotos, docs legales) =====
    path('editar/<int:prop_id>/', views.editar_propiedad, name='editar_propiedad'),
    path('editar/<int:prop_id>/subir-foto/', views.subir_foto_propiedad, name='subir_foto_propiedad'),
    path('editar/foto/<int:foto_id>/eliminar/', views.eliminar_foto_propiedad, name='eliminar_foto_propiedad'),
    path('editar/<int:prop_id>/subir-documento/', views.subir_documento_legal, name='subir_documento_legal'),
    path('editar/documento/<int:doc_id>/reemplazar/', views.reemplazar_documento_legal, name='reemplazar_documento_legal'),
    path('editar/documento/<int:doc_id>/eliminar/', views.eliminar_documento_legal, name='eliminar_documento_legal'),

    # ===== SWITCHES DE PERMISO (AJAX) =====
    path('editar/<int:prop_id>/toggle-permiso-corredor/', views.toggle_permiso_editar_corredor, name='toggle_permiso_editar_corredor'),
    path('editar/<int:prop_id>/toggle-permiso-dueno/', views.toggle_permiso_editar_dueno, name='toggle_permiso_editar_dueno'),

    # Favoritas
    path('toggle-favorita/<int:prop_id>/', views.toggle_favorita, name='toggle_favorita'),

    # ===== AFICHE / POSTER PDF =====
    path('afiche/<int:prop_id>/', views.generar_afiche, name='generar_afiche'),

    # ===== MARKETING IMAGES (Instagram Story + Facebook Afiche) =====
    path('story-ig/<int:prop_id>/', views.generar_story_instagram, name='generar_story_instagram'),
    path('afiche-fb/<int:prop_id>/', views.generar_afiche_facebook, name='generar_afiche_facebook'),
]
