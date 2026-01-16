from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone


class Servicio(models.Model):
    """Servicios disponibles para reservar"""
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    duracion_minutos = models.IntegerField(
        validators=[MinValueValidator(15)],
        help_text="Duración en minutos"
    )
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField(upload_to='servicios/', blank=True, null=True)
    activo = models.BooleanField(default=True)
    capacidad_maxima = models.IntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Servicios"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class HorarioDisponible(models.Model):
    """Horarios disponibles por día de la semana"""
    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Horarios Disponibles"
        unique_together = ['servicio', 'dia_semana', 'hora_inicio']
        ordering = ['dia_semana', 'hora_inicio']

    def __str__(self):
        return f"{self.servicio.nombre} - {self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fin}"


class Reservacion(models.Model):
    """Reservaciones de clientes"""
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
        ('completada', 'Completada'),
    ]
    
    ESTADOS_PAGO = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando'),
        ('pagado', 'Pagado'),
        ('fallido', 'Fallido'),
        ('reembolsado', 'Reembolsado'),
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservaciones')
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT)
    
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    
    nombre_cliente = models.CharField(max_length=200)
    email_cliente = models.EmailField()
    telefono_cliente = models.CharField(max_length=20)
    numero_personas = models.IntegerField(validators=[MinValueValidator(1)], default=1)
    
    notas = models.TextField(blank=True, help_text="Notas adicionales del cliente")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    
    # NUEVOS CAMPOS DE PAGO
    estado_pago = models.CharField(max_length=20, choices=ESTADOS_PAGO, default='pendiente')
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    transaccion_id = models.CharField(max_length=255, blank=True, null=True, help_text="ID de la transacción en la pasarela")
    referencia_pago = models.CharField(max_length=255, blank=True, null=True, help_text="Referencia del pago")
    fecha_pago = models.DateTimeField(blank=True, null=True)
    metodo_pago = models.CharField(max_length=50, blank=True, null=True, help_text="Tarjeta, PayPhone, etc.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Reservaciones"
        ordering = ['-fecha', '-hora_inicio']
        indexes = [
            models.Index(fields=['fecha', 'estado']),
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['transaccion_id']),
        ]

    def __str__(self):
        return f"{self.nombre_cliente} - {self.servicio.nombre} - {self.fecha} {self.hora_inicio}"

    def esta_confirmada(self):
        return self.estado == 'confirmada'
    
    def esta_pagada(self):
        return self.estado_pago == 'pagado'

    def puede_cancelar(self):
        """Verificar si la reservación puede ser cancelada (ej: 24h antes)"""
        from datetime import datetime, timedelta
        
        fecha_hora_reserva = datetime.combine(self.fecha, self.hora_inicio)
        
        if timezone.is_naive(fecha_hora_reserva):
            fecha_hora_reserva = timezone.make_aware(fecha_hora_reserva)
        
        limite_cancelacion = fecha_hora_reserva - timedelta(hours=24)
        
        return timezone.now() < limite_cancelacion