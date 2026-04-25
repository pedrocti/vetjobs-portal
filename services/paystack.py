"""Paystack payment service for handling all payment transactions."""

import requests
import os
import secrets
import hashlib
import hmac
from datetime import datetime
from typing import Dict, Optional, Tuple


class PaystackService:
    """Paystack payment integration service."""
    
    def __init__(self):
        # Use test keys for development
        self.secret_key = os.environ.get('PAYSTACK_SECRET_KEY', 'sk_test_your_secret_key_here')
        self.public_key = os.environ.get('PAYSTACK_PUBLIC_KEY', 'pk_test_your_public_key_here')
        self.base_url = 'https://api.paystack.co'
        
        # Default headers for API requests
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
    
    def generate_reference(self, prefix: str = 'VET') -> str:
        """Generate a unique payment reference."""
        timestamp = int(datetime.now().timestamp())
        random_string = secrets.token_hex(4).upper()
        return f"{prefix}_{timestamp}_{random_string}"
    
    def initialize_payment(self, email: str, amount: int, reference: str, 
                          callback_url: str, metadata: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """Initialize a payment transaction with Paystack."""
        
        # Convert amount to kobo (Paystack expects amount in smallest currency unit)
        amount_in_kobo = int(amount * 100)
        
        payload = {
            'email': email,
            'amount': amount_in_kobo,
            'reference': reference,
            'callback_url': callback_url,
            'metadata': metadata or {}
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/transaction/initialize',
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return True, data['data']
                else:
                    return False, {'error': data.get('message', 'Unknown error')}
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}
    
    def verify_payment(self, reference: str) -> Tuple[bool, Dict]:
        """Verify a payment transaction with Paystack."""
        
        try:
            response = requests.get(
                f'{self.base_url}/transaction/verify/{reference}',
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return True, data['data']
                else:
                    return False, {'error': data.get('message', 'Verification failed')}
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}
    
    def create_customer(self, email: str, first_name: str, last_name: str, 
                       phone: Optional[str] = None) -> Tuple[bool, Dict]:
        """Create a customer on Paystack."""
        
        payload = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name
        }
        
        if phone:
            payload['phone'] = phone
            
        try:
            response = requests.post(
                f'{self.base_url}/customer',
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data.get('status'):
                    return True, data['data']
                else:
                    return False, {'error': data.get('message', 'Customer creation failed')}
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}
    
    def create_plan(self, name: str, amount: int, interval: str = 'monthly') -> Tuple[bool, Dict]:
        """Create a subscription plan on Paystack."""
        
        # Convert amount to kobo
        amount_in_kobo = int(amount * 100)
        
        payload = {
            'name': name,
            'amount': amount_in_kobo,
            'interval': interval,
            'currency': 'NGN'
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/plan',
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data.get('status'):
                    return True, data['data']
                else:
                    return False, {'error': data.get('message', 'Plan creation failed')}
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}
    
    def create_subscription(self, customer_code: str, plan_code: str, 
                           authorization_code: str) -> Tuple[bool, Dict]:
        """Create a subscription for a customer."""
        
        payload = {
            'customer': customer_code,
            'plan': plan_code,
            'authorization': authorization_code
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/subscription',
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data.get('status'):
                    return True, data['data']
                else:
                    return False, {'error': data.get('message', 'Subscription creation failed')}
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}
    
    def cancel_subscription(self, subscription_code: str, email_token: str) -> Tuple[bool, Dict]:
        """Cancel a subscription."""
        
        payload = {
            'code': subscription_code,
            'token': email_token
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/subscription/disable',
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return True, data.get('data', {})
                else:
                    return False, {'error': data.get('message', 'Subscription cancellation failed')}
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}
    
    def validate_webhook(self, payload: str, signature: str) -> bool:
        """Validate Paystack webhook signature."""
        
        webhook_secret = os.environ.get('PAYSTACK_WEBHOOK_SECRET', '')
        if not webhook_secret:
            return False
            
        # Create hash
        hash_object = hmac.new(
            webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512
        )
        
        computed_signature = hash_object.hexdigest()
        return hmac.compare_digest(computed_signature, signature)
    
    def get_transaction(self, transaction_id: str) -> Tuple[bool, Dict]:
        """Get transaction details by ID."""
        
        try:
            response = requests.get(
                f'{self.base_url}/transaction/{transaction_id}',
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return True, data['data']
                else:
                    return False, {'error': data.get('message', 'Transaction not found')}
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}
    
    def list_transactions(self, per_page: int = 50, page: int = 1) -> Tuple[bool, Dict]:
        """List transactions with pagination."""
        
        params = {
            'perPage': per_page,
            'page': page
        }
        
        try:
            response = requests.get(
                f'{self.base_url}/transaction',
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return True, data['data']
                else:
                    return False, {'error': data.get('message', 'Failed to list transactions')}
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}


# Singleton instance for use across the application
paystack_service = PaystackService()