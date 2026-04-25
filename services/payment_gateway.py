"""
Unified payment gateway service that dynamically chooses between Paystack and Flutterwave
based on admin settings.
"""

from models import PaymentSetting
from services.paystack import PaystackService
from services.flutterwave import FlutterwaveService
from typing import Dict, Optional, Tuple
from flask import current_app


class PaymentGatewayService:
    """Unified payment service that chooses gateway based on admin settings."""
    
    def __init__(self):
        self._paystack_service = None
        self._flutterwave_service = None
    
    def _get_paystack_service(self) -> PaystackService:
        """Get Paystack service with admin-configured keys."""
        if self._paystack_service is None:
            self._paystack_service = PaystackService()
            
            # Get admin-configured keys and mode
            mode = PaymentSetting.get_setting('paystack_mode', 'test')
            
            if mode == 'live':
                public_key = PaymentSetting.get_setting('paystack_public_key_live', '')
                secret_key = PaymentSetting.get_setting('paystack_secret_key_live', '')
            else:
                public_key = PaymentSetting.get_setting('paystack_public_key_test', '')
                secret_key = PaymentSetting.get_setting('paystack_secret_key_test', '')
            
            # Override with admin settings if available
            if public_key:
                self._paystack_service.public_key = str(public_key)
            if secret_key:
                self._paystack_service.secret_key = str(secret_key)
                self._paystack_service.headers['Authorization'] = f'Bearer {str(secret_key)}'
        
        return self._paystack_service
    
    def _get_flutterwave_service(self) -> FlutterwaveService:
        """Get Flutterwave service with admin-configured keys."""
        if self._flutterwave_service is None:
            self._flutterwave_service = FlutterwaveService()

            # Get admin-configured keys and mode
            mode = PaymentSetting.get_setting('flutterwave_mode', 'live')

            if mode == 'live':
                public_key = PaymentSetting.get_setting('flutterwave_public_key_live', '')
                secret_key = PaymentSetting.get_setting('flutterwave_secret_key_live', '')
            else:
                public_key = PaymentSetting.get_setting('flutterwave_public_key_test', '')
                secret_key = PaymentSetting.get_setting('flutterwave_secret_key_test', '')

            # Apply admin keys if available
            if public_key:
                self._flutterwave_service.public_key = str(public_key)
            if secret_key:
                self._flutterwave_service.secret_key = str(secret_key)
                # Update headers if applicable
                if hasattr(self._flutterwave_service, 'headers'):
                    self._flutterwave_service.headers['Authorization'] = f'Bearer {str(secret_key)}'

        return self._flutterwave_service

    
    def _get_active_gateway(self):
        """Get the currently active payment gateway based on admin settings."""
        gateway = PaymentSetting.get_setting('payment_gateway')
        
        if gateway == 'flutterwave':
            return self._get_flutterwave_service()
        else:
            return self._get_paystack_service()
    
    def get_public_key(self) -> str:
        """Get the public key for the active gateway."""
        gateway = self._get_active_gateway()
        
        return str(gateway.public_key)
    
    def get_gateway_name(self) -> str:
        """Get the name of the active gateway."""
        return str(PaymentSetting.get_setting('payment_gateway'))
    
    def generate_reference(self, prefix: str = 'VET') -> str:
        """Generate a unique payment reference."""
        gateway = self._get_active_gateway()
        return gateway.generate_reference(prefix)
    
    def initialize_payment(self, email: str, amount: int, reference: str, 
                          callback_url: str, metadata: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """Initialize a payment transaction with the active gateway."""
        gateway = self._get_active_gateway()
        gateway_name = self.get_gateway_name()
        
        try:
            current_app.logger.info(f"Initializing payment with {gateway_name}: {reference}")
            success, result = gateway.initialize_payment(email, amount, reference, callback_url, metadata)
            
            if success:
                current_app.logger.info(f"Payment initialized successfully with {gateway_name}")
            else:
                current_app.logger.error(f"Payment initialization failed with {gateway_name}: {result}")
            
            return success, result
            
        except Exception as e:
            current_app.logger.error(f"Payment initialization error with {gateway_name}: {str(e)}")
            return False, {'error': f'Payment initialization failed: {str(e)}'}
    
    def verify_payment(self, reference: str) -> Tuple[bool, Dict]:
        """Verify a payment transaction with the active gateway."""
        gateway = self._get_active_gateway()
        gateway_name = self.get_gateway_name()
        
        try:
            current_app.logger.info(f"Verifying payment with {gateway_name}: {reference}")
            success, result = gateway.verify_payment(reference)
            
            if success:
                current_app.logger.info(f"Payment verified successfully with {gateway_name}")
            else:
                current_app.logger.error(f"Payment verification failed with {gateway_name}: {result}")
            
            return success, result
            
        except Exception as e:
            current_app.logger.error(f"Payment verification error with {gateway_name}: {str(e)}")
            return False, {'error': f'Payment verification failed: {str(e)}'}
    
    def create_subscription_plan(self, name: str, amount: float, interval: str = 'monthly') -> Tuple[bool, Dict]:
        """Create a subscription plan with the active gateway."""
        gateway = self._get_active_gateway()
        gateway_name = self.get_gateway_name()
        
        try:
            current_app.logger.info(f"Creating subscription plan with {gateway_name}: {name}")
            
            if hasattr(gateway, 'create_subscription_plan'):
                success, result = gateway.create_subscription_plan(name, amount, interval)
            elif hasattr(gateway, 'create_plan'):
                success, result = gateway.create_plan(name, int(amount), interval)
            else:
                # Fallback for gateways that don't support subscription plans
                current_app.logger.warning(f"{gateway_name} doesn't support subscription plans")
                return False, {'error': f'{gateway_name} does not support subscription plans'}
            
            if success:
                current_app.logger.info(f"Subscription plan created successfully with {gateway_name}")
            else:
                current_app.logger.error(f"Subscription plan creation failed with {gateway_name}: {result}")
            
            return success, result
            
        except Exception as e:
            current_app.logger.error(f"Subscription plan creation error with {gateway_name}: {str(e)}")
            return False, {'error': f'Subscription plan creation failed: {str(e)}'}


# Create a global instance
payment_gateway_service = PaymentGatewayService()