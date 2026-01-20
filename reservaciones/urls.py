from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_servicios, name='lista_servicios'),
    path('servicio/<int:servicio_id>/', views.detalle_servicio, name='detalle_servicio'),
    path('servicio/<int:servicio_id>/reservar/', views.crear_reservacion, name='crear_reservacion'),
    path('api/horarios/<int:servicio_id>/', views.obtener_horarios_disponibles, name='horarios_disponibles'),
    path('mis-reservaciones/', views.mis_reservaciones, name='mis_reservaciones'),
    path('reservacion/<int:reservacion_id>/cancelar/', views.cancelar_reservacion, name='cancelar_reservacion'),
    path('registro/', views.registro, name='registro'),
    
    # Rutas de pago con Stripe
    path('reservacion/<int:reservacion_id>/pagar/', views.procesar_pago, name='procesar_pago'),
    path('pago/exito/<int:reservacion_id>/', views.pago_exitoso, name='pago_exitoso'),
    path('pago/cancelado/<int:reservacion_id>/', views.pago_cancelado, name='pago_cancelado'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
]