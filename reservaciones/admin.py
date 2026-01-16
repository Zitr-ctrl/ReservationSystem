from django.contrib import admin
from .models import Servicio, HorarioDisponible, Reservacion

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'precio', 'duracion_minutos', 'capacidad_maxima', 'activo']
    list_filter = ['activo', 'created_at']
    search_fields = ['nombre', 'descripcion']

@admin.register(HorarioDisponible)
class HorarioDisponibleAdmin(admin.ModelAdmin):
    list_display = ['servicio', 'dia_semana', 'hora_inicio', 'hora_fin', 'activo']
    list_filter = ['dia_semana', 'activo']

@admin.register(Reservacion)
class ReservacionAdmin(admin.ModelAdmin):
    list_display = ['nombre_cliente', 'servicio', 'fecha', 'hora_inicio', 'estado', 'estado_pago', 'precio_total']
    list_filter = ['estado', 'estado_pago', 'fecha', 'servicio']
    search_fields = ['nombre_cliente', 'email_cliente', 'telefono_cliente', 'transaccion_id']
    date_hierarchy = 'fecha'
    readonly_fields = ['transaccion_id', 'referencia_pago', 'fecha_pago']
    
    fieldsets = (
        ('Información del Servicio', {
            'fields': ('servicio', 'fecha', 'hora_inicio', 'hora_fin', 'numero_personas')
        }),
        ('Información del Cliente', {
            'fields': ('usuario', 'nombre_cliente', 'email_cliente', 'telefono_cliente', 'notas')
        }),
        ('Estado', {
            'fields': ('estado', 'estado_pago')
        }),
        ('Información de Pago', {
            'fields': ('precio_total', 'metodo_pago', 'transaccion_id', 'referencia_pago', 'fecha_pago')
        }),
    )
    
    actions = ['confirmar_reservaciones', 'completar_reservaciones', 'marcar_como_pagadas']
    
    def confirmar_reservaciones(self, request, queryset):
        queryset.update(estado='confirmada')
    confirmar_reservaciones.short_description = "Confirmar reservaciones seleccionadas"
    
    def completar_reservaciones(self, request, queryset):
        queryset.update(estado='completada')
    completar_reservaciones.short_description = "Marcar como completadas"
    
    def marcar_como_pagadas(self, request, queryset):
        queryset.update(estado_pago='pagado')
    marcar_como_pagadas.short_description = "Marcar como pagadas (manual)"