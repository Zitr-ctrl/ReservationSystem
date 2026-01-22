import requests
import time
from django.conf import settings


class PayPhoneService:
    """
    Servicio para integración con PayPhone Ecuador
    Basado en la documentación oficial de PayPhone
    """

    def __init__(self):
        self.token = settings.PAYPHONE_TOKEN
        self.store_id = settings.PAYPHONE_STORE_ID
        self.api_url = getattr(
            settings,
            'PAYPHONE_API_URL',
            'https://pay.payphonetodoesposible.com/api'
        )

        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

    def crear_pago(self, reservacion, return_url, cancel_url):
        """
        Crear una solicitud de pago en PayPhone
        Payload según documentación oficial
        """
        try:
            # PayPhone trabaja en centavos
            monto_centavos = int(reservacion.precio_total * 100)

            # ID único de transacción
            client_transaction_id = f"RES-{reservacion.id}-{int(time.time())}"

            # Payload según documentación oficial de PayPhone
            payload = {
                "clientTransactionId": client_transaction_id,
                "storeId": self.store_id,
                "reference": f"Reservación #{reservacion.id} - {reservacion.servicio.nombre}",
                "responseUrl": return_url,
                "amount": monto_centavos,
                "amountWithoutTax": monto_centavos
            }

            # Debug
            print("PayPhone Payload:", payload)

            response = requests.post(
                f"{self.api_url}/button/Prepare",
                json=payload,
                headers=self.headers,
                timeout=30
            )

            print("PayPhone Response Status:", response.status_code)
            print("PayPhone Response Body:", response.text)

            if response.status_code == 200:
                data = response.json()

                return {
                    "success": True,
                    "payment_url": data.get("payWithCard"),
                    "transaction_id": data.get("paymentId"),
                    "client_transaction_id": client_transaction_id
                }
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", response.text)
                except Exception:
                    error_msg = response.text

                return {
                    "success": False,
                    "error": error_msg
                }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Tiempo de espera agotado al conectar con PayPhone"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Error de conexión: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def confirmar_pago(self, transaction_id, client_transaction_id):
        """
        Confirmar el estado de un pago en PayPhone
        Usa POST según la documentación
        """
        try:
            # Payload para confirmar
            payload = {
                "id": transaction_id,
                "clientTxId": client_transaction_id
            }
            
            print("Confirm Payload:", payload)
            
            response = requests.post(
                f"{self.api_url}/button/V2/Confirm",
                json=payload,
                headers=self.headers,
                timeout=30
            )

            print("Confirm Response Status:", response.status_code)
            print("Confirm Response Body:", response.text)

            if response.status_code == 200:
                data = response.json()

                status = (
                    data.get("transactionStatus")
                    or data.get("statusCode")
                    or "Unknown"
                )

                # PayPhone puede devolver diferentes valores para aprobado
                is_approved = str(status).lower() in [
                    "approved", "aprobado", "3", "approved"
                ] or data.get("statusCode") == 3

                return {
                    "success": True,
                    "status": status,
                    "is_approved": is_approved,
                    "authorization_code": data.get("authorizationCode"),
                    "transaction_id": data.get("transactionId"),
                    "amount": (
                        data.get("amount", 0) / 100
                        if data.get("amount")
                        else 0
                    ),
                    "data": data
                }

            return {
                "success": False,
                "error": f"Error al confirmar pago: {response.text}"
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Error de conexión: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def procesar_respuesta(self, request_data):
        """
        Procesar la respuesta de PayPhone (redirect)
        """
        return {
            "transaction_id": request_data.get("id"),
            "client_transaction_id": request_data.get("clientTransactionId"),
            "status_code": request_data.get("statusCode"),
            "transaction_status": request_data.get("transactionStatus"),
            "authorization_code": request_data.get("authorizationCode"),
            "amount": (
                int(request_data.get("amount", 0)) / 100
                if request_data.get("amount")
                else 0
            )
        }