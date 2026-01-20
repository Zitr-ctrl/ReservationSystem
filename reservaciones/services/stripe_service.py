import stripe
from django.conf import settings
from decimal import Decimal
from urllib.parse import urlparse


class StripeService:
    """Servicio para integración con Stripe"""
    
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.public_key = settings.STRIPE_PUBLIC_KEY
    
    def crear_checkout_session(self, reservacion, success_url, cancel_url):
        """
        Crear una sesión de checkout de Stripe
        """
        try:
            # Convertir a centavos (Stripe trabaja en centavos)
            monto_centavos = int(reservacion.precio_total * 100)
            
            # Construir URL absoluta de la imagen si existe
            images = []
            if reservacion.servicio.imagen:
                parsed = urlparse(success_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                images = [f"{base_url}{reservacion.servicio.imagen.url}"]
            
            # Crear sesión de checkout
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': monto_centavos,
                        'product_data': {
                            'name': f'{reservacion.servicio.nombre}',
                            'description': f'Reservación para {reservacion.nombre_cliente} el {reservacion.fecha} a las {reservacion.hora_inicio}',
                            'images': images,
                        },
                    },
                    'quantity': reservacion.numero_personas,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=reservacion.email_cliente,
                metadata={
                    'reservacion_id': reservacion.id,
                    'usuario_id': reservacion.usuario.id,
                },
                # Configuración adicional
                payment_intent_data={
                    'metadata': {
                        'reservacion_id': reservacion.id,
                    }
                }
            )
            
            return {
                'success': True,
                'session_id': session.id,
                'checkout_url': session.url,
                'payment_intent': session.payment_intent
            }
        
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def verificar_pago(self, session_id):
        """
        Verificar el estado de un pago mediante session_id
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            
            return {
                'success': True,
                'status': session.payment_status,
                'payment_intent': session.payment_intent,
                'data': session
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def obtener_payment_intent(self, payment_intent_id):
        """
        Obtener información de un Payment Intent
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                'success': True,
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100,  # Convertir de centavos
                'data': payment_intent
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def crear_reembolso(self, payment_intent_id, monto=None):
        """
        Crear un reembolso
        """
        try:
            refund_data = {'payment_intent': payment_intent_id}
            
            if monto:
                # Convertir a centavos
                refund_data['amount'] = int(monto * 100)
            
            refund = stripe.Refund.create(**refund_data)
            
            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'data': refund
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }