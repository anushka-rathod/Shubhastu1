"""
Razorpay Payment Gateway integration service for Shubhashtu Fashion.
Implements:
- Server-side order creation via Razorpay REST API
- Cryptographic HMAC-SHA256 payment signature verification
- Webhook signature verification
- Cash on Delivery handling
"""
import hmac
import hashlib
import json
import logging
try:
    import requests
except ImportError:
    requests = None
from config import Config

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, key_id: str = None, key_secret: str = None):
        self.key_id = key_id or Config.RAZORPAY_KEY_ID
        self.key_secret = key_secret or Config.RAZORPAY_KEY_SECRET

    def is_razorpay_configured(self) -> bool:
        """Returns True only if both Razorpay Key ID and Secret are provided."""
        return bool(self.key_id and self.key_secret and self.key_id.strip() and self.key_secret.strip())

    def create_order(self, amount_inr: float, receipt: str = None, receipt_id: str = None, notes: dict = None, **kwargs) -> dict:
        """
        Creates a server-side Razorpay order.
        Amount is converted to paise (INR 100 = 10000 paise).
        Accepts either 'receipt' or 'receipt_id' for receipt reference.
        """
        if not self.is_razorpay_configured():
            return {
                'success': False,
                'configured': False,
                'error': 'Razorpay API keys (Key ID and Key Secret) are not yet configured in store settings or .env file.'
            }

        receipt_val = str(receipt or receipt_id or 'order_rcpt')[:40]
        amount_paise = int(round(amount_inr * 100))
        payload = {
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': receipt_val,
            'notes': notes or {}
        }

        try:
            resp = requests.post(
                'https://api.razorpay.com/v1/orders',
                auth=(self.key_id, self.key_secret),
                json=payload,
                timeout=10
            )

            if resp.status_code in (200, 201):
                order_data = resp.json()
                return {
                    'success': True,
                    'configured': True,
                    'order_id': order_data['id'],
                    'amount_paise': order_data['amount'],
                    'currency': order_data['currency'],
                    'key_id': self.key_id
                }
            else:
                error_msg = resp.text
                try:
                    error_json = resp.json()
                    error_msg = error_json.get('error', {}).get('description', resp.text)
                except Exception:
                    pass
                logger.error("Razorpay order creation failed: %s", error_msg)
                return {
                    'success': False,
                    'configured': True,
                    'error': f"Razorpay API Error: {error_msg}"
                }
        except Exception as e:
            logger.exception("Failed to connect to Razorpay API: %s", e)
            return {
                'success': False,
                'configured': True,
                'error': f"Could not connect to Razorpay payment gateway: {str(e)}"
            }

    def verify_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        """
        Server-side cryptographic verification of Razorpay payment signature.
        Never simulates success.
        """
        if not self.is_razorpay_configured():
            return False

        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return False

        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
        generated_signature = hmac.new(
            self.key_secret.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(generated_signature, razorpay_signature)

    def verify_webhook_signature(self, request_body: bytes, signature_header: str, webhook_secret: str) -> bool:
        """Verifies Razorpay webhook payload authenticity."""
        if not webhook_secret or not signature_header:
            return False

        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            request_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature_header)

