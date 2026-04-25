"""
Flutterwave payment integration service.
"""

import requests
import secrets
from datetime import datetime
from typing import Dict, Optional, Tuple
from flask import current_app


class FlutterwaveService:
    """Flutterwave payment integration service."""

    def __init__(self):
        self.secret_key = None
        self.public_key = None
        self.base_url = 'https://api.flutterwave.com/v3'
        self.mode = 'test'
        self._initialized = False
        self.headers = {}

    def _load_settings(self):
        """Load Flutterwave settings from DB safely."""
        if self._initialized:
            return

        try:
            from models import PaymentSetting

           
            self.mode = PaymentSetting.get_setting('flutterwave_mode', 'test')

        
            self.secret_key = PaymentSetting.get_setting(f'flutterwave_secret_key_{self.mode}')
            self.public_key = PaymentSetting.get_setting(f'flutterwave_public_key_{self.mode}')

            
            if not self.secret_key:
                raise Exception(f"Missing Flutterwave {self.mode} secret key")

            if not self.public_key:
                raise Exception(f"Missing Flutterwave {self.mode} public key")

            
            self.secret_key = str(self.secret_key).strip()
            self.public_key = str(self.public_key).strip()

           
            self.headers = {
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json',
            }

            
            current_app.logger.info(f"Flutterwave mode: {self.mode}")
            current_app.logger.info(f"Flutterwave key loaded: {self.secret_key[:12]}...")

            self._initialized = True

        except Exception as e:
            current_app.logger.error(f"Flutterwave config error: {str(e)}")
            raise 

    def generate_reference(self, prefix: str = 'VET') -> str:
        """Generate a unique payment reference."""
        timestamp = int(datetime.now().timestamp())
        random_string = secrets.token_hex(4).upper()
        return f"{prefix}_{timestamp}_{random_string}"

    def initialize_payment(
        self,
        email: str,
        amount: int,
        reference: str,
        callback_url: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Dict]:
        """Initialize a payment transaction with Flutterwave."""

        self._load_settings()

        payload = {
            'tx_ref': reference,
            'amount': str(amount),
            'currency': 'NGN',
            'redirect_url': callback_url,
            'payment_options': 'card,banktransfer,ussd',
            'customer': {
                'email': email
            },
            'customizations': {
                'title': 'Veteran Job Portal',
                'description': 'Payment for services',
                'logo': 'https://vetjobportal.com/logo.png'
            },
            'meta': metadata or {}
        }

        # ✅ Safe debug
        print("🟢 DEBUG - Mode:", self.mode)
        print("🟢 DEBUG - Secret Key:", self.secret_key[:10] if self.secret_key else "NONE")

        try:
            response = requests.post(
                f'{self.base_url}/payments',
                json=payload,
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('status') == 'success':
                    current_app.logger.debug("Flutterwave payment initialized successfully")

                    result = data['data'].copy()

                    # Normalize response
                    if 'link' in result:
                        result['authorization_url'] = result['link']

                    return True, result

                return False, {'error': data.get('message', 'Unknown error')}

            return False, {'error': f'HTTP {response.status_code}: {response.text}'}

        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}

    def verify_payment(self, reference: str) -> Tuple[bool, Dict]:
        """Verify a payment transaction."""

        self._load_settings()

        try:
            response = requests.get(
                f'{self.base_url}/transactions/verify_by_reference?tx_ref={reference}',
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('status') == 'success':
                    return True, data['data']

                return False, {'error': data.get('message', 'Verification failed')}

            return False, {'error': f'HTTP {response.status_code}: {response.text}'}

        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}

    def get_transaction_status(self, transaction_id: str) -> Tuple[bool, Dict]:
        """Get transaction status."""

        self._load_settings()

        try:
            response = requests.get(
                f'{self.base_url}/transactions/{transaction_id}/verify',
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('status') == 'success':
                    return True, data['data']

                return False, {'error': data.get('message', 'Status check failed')}

            return False, {'error': f'HTTP {response.status_code}: {response.text}'}

        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}

    def create_subscription_plan(self, name: str, amount: float, interval: str = 'monthly') -> Tuple[bool, Dict]:
        """Create a subscription plan."""

        self._load_settings()

        payload = {
            'amount': int(amount),
            'name': name,
            'interval': interval,
            'currency': 'NGN'
        }

        try:
            response = requests.post(
                f'{self.base_url}/payment-plans',
                json=payload,
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('status') == 'success':
                    return True, data['data']

                return False, {'error': data.get('message', 'Plan creation failed')}

            return False, {'error': f'HTTP {response.status_code}: {response.text}'}

        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}


# Global instance
flutterwave_service = FlutterwaveService()