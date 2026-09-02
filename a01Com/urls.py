from django.urls import path
from . import views
from .views_contacto import (
    enviar_consulta_email,
    gestion_consultas,
    detalle_consulta,
    responder_consulta,
)

urlpatterns = [
    path('', views.centro_comunicaciones, name='centro_comunicaciones'),
    path('enviar/', views.enviar_comunicacion, name='enviar_comunicacion'),
    path('marcar-leido/<int:com_id>/', views.marcar_leido, name='marcar_leido'),
    path('marcar-no-leido/<int:com_id>/', views.marcar_no_leido, name='marcar_no_leido'),
    path('eliminar/<int:com_id>/', views.eliminar_comunicacion, name='eliminar_comunicacion'),
    path('contacto/email/', enviar_consulta_email, name='enviar_consulta_email'),
    path('consultas/', gestion_consultas, name='gestion_consultas'),
    path('consultas/<int:consulta_id>/', detalle_consulta, name='detalle_consulta'),
    path('consultas/<int:consulta_id>/responder/', responder_consulta, name='responder_consulta'),
]
