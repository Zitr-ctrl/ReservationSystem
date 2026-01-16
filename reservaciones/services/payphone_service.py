import requests
import hashlib
import json
from django.conf import settings
from decimal import Decimal


class PayPhoneService:
    """Servicio para integración con PayPhone"""
    
    def __init__(self):
        self.api_url = settings.PAYPHONE_API_URL
        self.token = settings.PAYPHONE_TOKEN
        self.store_id = settings.PAYPHONE_STORE_ID
    
    def crear_pago(self, reservacion):
        """
        Crear un link de pago para una reservación
        """
        # Preparar datos del pago
        monto = float(reservacion.precio_total)
        
        payload = {
            'amount': monto,
            'amountWithoutTax': monto / 1.12,  # Restar IVA 12%
            'currency': 'USD',
            'clientTransactionId': f'RES-{reservacion.id}',
            'reference': f'Reservación #{reservacion.id} - {reservacion.servicio.nombre}',
            'email': reservacion.email_cliente,
            'phoneNumber': reservacion.telefono_cliente,
            'responseUrl': f"{settings.SITE_URL}/reservaciones/pago/respuesta/",
            'cancellationUrl': f"{settings.SITE_URL}/reservaciones/pago/cancelado/{reservacion.id}/",
        }
        
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                f'{self.api_url}/button/Prepare',
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'payment_url': data.get('payWithCard'),
                    'transaction_id': data.get('transactionId'),
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'error': response.text
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def verificar_pago(self, transaction_id):
        """
        Verificar el estado de un pago
        """
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            response = requests.post(
                f'{self.api_url}/Sale/Confirm',
                json={'id': transaction_id, 'clientTxId': transaction_id},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'status': data.get('statusCode'),
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'error': response.text
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }