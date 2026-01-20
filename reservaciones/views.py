from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.contrib.auth.models import User 
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django import forms
from django.conf import settings
import stripe
import json

from .models import Servicio, Reservacion, HorarioDisponible
from .services.stripe_service import StripeService


def lista_servicios(request):
    """Mostrar todos los servicios disponibles"""
    servicios = Servicio.objects.filter(activo=True)
    return render(request, 'reservaciones/lista_servicios.html', {
        'servicios': servicios
    })


def detalle_servicio(request, servicio_id):
    """Detalle de un servicio específico"""
    servicio = get_object_or_404(Servicio, id=servicio_id, activo=True)
    return render(request, 'reservaciones/detalle_servicio.html', {
        'servicio': servicio
    })


@login_required
def crear_reservacion(request, servicio_id):
    """Crear una nueva reservación"""
    servicio = get_object_or_404(Servicio, id=servicio_id, activo=True)
    
    if request.method == 'POST':
        fecha = request.POST.get('fecha')
        hora_inicio = request.POST.get('hora_inicio')
        nombre_cliente = request.POST.get('nombre_cliente')
        email_cliente = request.POST.get('email_cliente')
        telefono_cliente = request.POST.get('telefono_cliente')
        numero_personas = int(request.POST.get('numero_personas', 1))
        notas = request.POST.get('notas', '')
        
        # Validar número de personas
        if numero_personas > servicio.capacidad_maxima:
            messages.error(request, f'El número de personas excede la capacidad máxima ({servicio.capacidad_maxima}).')
            return redirect('crear_reservacion', servicio_id=servicio.id)
        
        if numero_personas < 1:
            messages.error(request, 'El número de personas debe ser al menos 1.')
            return redirect('crear_reservacion', servicio_id=servicio.id)
        
        # Calcular hora fin
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M').time()
        hora_fin_obj = (
            datetime.combine(fecha_obj, hora_inicio_obj) + 
            timedelta(minutes=servicio.duracion_minutos)
        ).time()
        
        # Verificar que la fecha no sea en el pasado
        if fecha_obj < timezone.now().date():
            messages.error(request, 'No puedes reservar en fechas pasadas.')
            return redirect('crear_reservacion', servicio_id=servicio.id)
        
        # Verificar disponibilidad
        conflictos = Reservacion.objects.filter(
            servicio=servicio,
            fecha=fecha_obj,
            estado__in=['pendiente', 'confirmada']
        ).filter(
            Q(hora_inicio__lt=hora_fin_obj, hora_fin__gt=hora_inicio_obj)
        )
        
        if conflictos.exists():
            messages.error(request, 'El horario seleccionado ya no está disponible.')
            return redirect('crear_reservacion', servicio_id=servicio.id)
        
        # Crear reservación
        reservacion = Reservacion.objects.create(
            usuario=request.user,
            servicio=servicio,
            fecha=fecha_obj,
            hora_inicio=hora_inicio_obj,
            hora_fin=hora_fin_obj,
            nombre_cliente=nombre_cliente,
            email_cliente=email_cliente,
            telefono_cliente=telefono_cliente,
            numero_personas=numero_personas,
            notas=notas,
            precio_total=servicio.precio * numero_personas,
            estado='pendiente'
        )
        
        messages.success(request, f'¡Reservación creada exitosamente! Tu reservación #{reservacion.id} está pendiente de confirmación.')
        return redirect('mis_reservaciones')
    
    return render(request, 'reservaciones/crear_reservacion.html', {
        'servicio': servicio,
        'today': timezone.now().date()
    })


def obtener_horarios_disponibles(request, servicio_id):
    """API para obtener horarios disponibles (AJAX)"""
    servicio = get_object_or_404(Servicio, id=servicio_id)
    fecha_str = request.GET.get('fecha')
    
    if not fecha_str:
        return JsonResponse({'error': 'Fecha requerida'}, status=400)
    
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    dia_semana = fecha.weekday()
    
    # Obtener horarios configurados para ese día
    horarios = HorarioDisponible.objects.filter(
        servicio=servicio,
        dia_semana=dia_semana,
        activo=True
    )
    
    horarios_disponibles = []
    for horario in horarios:
        # Generar slots de tiempo según duración del servicio
        hora_actual = horario.hora_inicio
        while hora_actual < horario.hora_fin:
            hora_fin_slot = (
                datetime.combine(fecha, hora_actual) + 
                timedelta(minutes=servicio.duracion_minutos)
            ).time()
            
            if hora_fin_slot <= horario.hora_fin:
                # Verificar si está disponible
                conflicto = Reservacion.objects.filter(
                    servicio=servicio,
                    fecha=fecha,
                    estado__in=['pendiente', 'confirmada']
                ).filter(
                    Q(hora_inicio__lt=hora_fin_slot, hora_fin__gt=hora_actual)
                ).exists()
                
                if not conflicto:
                    horarios_disponibles.append({
                        'hora': hora_actual.strftime('%H:%M'),
                        'disponible': True
                    })
            
            # Incrementar por intervalos (ej: cada 30 min)
            hora_actual = (
                datetime.combine(fecha, hora_actual) + timedelta(minutes=30)
            ).time()
    
    return JsonResponse({'horarios': horarios_disponibles})


@login_required
def mis_reservaciones(request):
    """Ver las reservaciones del usuario"""
    reservaciones = Reservacion.objects.filter(
        usuario=request.user
    ).select_related('servicio')
    
    return render(request, 'reservaciones/mis_reservaciones.html', {
        'reservaciones': reservaciones
    })


@login_required
def cancelar_reservacion(request, reservacion_id):
    """Cancelar una reservación"""
    reservacion = get_object_or_404(Reservacion, id=reservacion_id, usuario=request.user)
    
    if not reservacion.puede_cancelar():
        messages.error(request, 'No se puede cancelar con menos de 24 horas de anticipación.')
        return redirect('mis_reservaciones')
    
    if request.method == 'POST':
        reservacion.estado = 'cancelada'
        reservacion.save()
        messages.success(request, 'Reservación cancelada exitosamente.')
        return redirect('mis_reservaciones')
    
    return render(request, 'reservaciones/cancelar_reservacion.html', {
        'reservacion': reservacion
    })


# Formulario de registro personalizado
class RegistroForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'tu@email.com'
        })
    )
    first_name = forms.CharField(
        required=True,
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Juan'
        })
    )
    last_name = forms.CharField(
        required=True,
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Pérez'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'usuario123'
            }),
        }

    def __init__(self, *args, **kwargs):
        super(RegistroForm, self).__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '••••••••'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '••••••••'
        })

    def save(self, commit=True):
        user = super(RegistroForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


def registro(request):
    """Vista para registrar nuevos usuarios"""
    if request.user.is_authenticated:
        return redirect('lista_servicios')
    
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Iniciar sesión automáticamente después del registro
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, f'¡Bienvenido {user.first_name}! Tu cuenta ha sido creada exitosamente.')
            return redirect('lista_servicios')
        else:
            # Agregar mensajes de error específicos
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = RegistroForm()
    
    return render(request, 'registration/registro.html', {'form': form})


@login_required
def procesar_pago(request, reservacion_id):
    """Procesar el pago de una reservación con Stripe"""
    reservacion = get_object_or_404(Reservacion, id=reservacion_id, usuario=request.user)
    
    # Verificar que la reservación no esté pagada
    if reservacion.esta_pagada():
        messages.info(request, 'Esta reservación ya está pagada.')
        return redirect('mis_reservaciones')
    
    # Crear sesión de checkout con Stripe
    stripe_service = StripeService()
    
    # URLs de retorno - USANDO SITE_URL del settings
    base_url = settings.SITE_URL.rstrip('/')  # Quitar barra final si existe
    success_url = f"{base_url}/reservaciones/pago/exito/{reservacion.id}/"
    cancel_url = f"{base_url}/reservaciones/pago/cancelado/{reservacion.id}/"
    
    # Debug - Ver las URLs generadas
    print(f"Success URL: {success_url}")
    print(f"Cancel URL: {cancel_url}")
    
    resultado = stripe_service.crear_checkout_session(
        reservacion=reservacion,
        success_url=success_url,
        cancel_url=cancel_url
    )
    
    if resultado['success']:
        # Guardar el session_id
        reservacion.transaccion_id = resultado['session_id']
        reservacion.estado_pago = 'procesando'
        reservacion.save()
        
        # Redirigir al checkout de Stripe
        return redirect(resultado['checkout_url'])
    else:
        messages.error(request, f'Error al procesar el pago: {resultado["error"]}')
        print(f"Error de Stripe: {resultado['error']}")  # Debug
        return redirect('mis_reservaciones')

@login_required
def pago_exitoso(request, reservacion_id):
    """Página de confirmación después de pago exitoso"""
    reservacion = get_object_or_404(Reservacion, id=reservacion_id, usuario=request.user)
    
    # Verificar el pago con Stripe
    if reservacion.transaccion_id:
        stripe_service = StripeService()
        verificacion = stripe_service.verificar_pago(reservacion.transaccion_id)
        
        if verificacion['success'] and verificacion['status'] == 'paid':
            reservacion.estado_pago = 'pagado'
            reservacion.estado = 'confirmada'
            reservacion.fecha_pago = timezone.now()
            reservacion.metodo_pago = 'Stripe'
            reservacion.save()
            
            messages.success(request, '¡Pago procesado exitosamente! Tu reservación ha sido confirmada.')
        else:
            messages.warning(request, 'El pago está siendo procesado. Te notificaremos cuando se confirme.')
    
    return redirect('mis_reservaciones')


@login_required
def pago_cancelado(request, reservacion_id):
    """Cuando el usuario cancela el pago"""
    reservacion = get_object_or_404(Reservacion, id=reservacion_id, usuario=request.user)
    
    # Actualizar estado
    reservacion.estado_pago = 'pendiente'
    reservacion.save()
    
    messages.warning(request, 'El pago fue cancelado. Puedes intentar de nuevo cuando desees.')
    return redirect('mis_reservaciones')


@csrf_exempt
def stripe_webhook(request):
    """Webhook para recibir eventos de Stripe"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Payload inválido
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Firma inválida
        return HttpResponse(status=400)
    
    # Manejar el evento
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Obtener reservación
        reservacion_id = session['metadata']['reservacion_id']
        
        try:
            reservacion = Reservacion.objects.get(id=reservacion_id)
            
            # Actualizar reservación
            reservacion.estado_pago = 'pagado'
            reservacion.estado = 'confirmada'
            reservacion.fecha_pago = timezone.now()
            reservacion.metodo_pago = 'Stripe'
            reservacion.referencia_pago = session.get('payment_intent')
            reservacion.save()
            
        except Reservacion.DoesNotExist:
            pass
    
    elif event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        # Manejar pago exitoso
        pass
    
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        # Manejar pago fallido
        try:
            reservacion_id = payment_intent['metadata']['reservacion_id']
            reservacion = Reservacion.objects.get(id=reservacion_id)
            reservacion.estado_pago = 'fallido'
            reservacion.save()
        except:
            pass
    
    return HttpResponse(status=200)