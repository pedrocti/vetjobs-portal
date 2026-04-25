import os
from flask import current_app
from twilio.rest import Client

class SMSService:
    """Service for sending SMS notifications using Twilio"""
    
    def __init__(self):
        self.account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        self.auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        self.phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
        
        if self.account_sid and self.auth_token and self.phone_number:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            # Use print for initialization without app context
            print("Twilio credentials not configured. SMS notifications will be logged only.")
    
    def send_notification_sms(self, phone_number, message, category='general'):
        """
        Send SMS notification
        
        Args:
            phone_number: Recipient phone number
            message: SMS message text
            category: Notification category for logging
        """
        
        if not phone_number:
            current_app.logger.warning("No phone number provided for SMS")
            return False
        
        # Clean phone number
        phone_number = self._clean_phone_number(phone_number)
        
        if not self.client:
            # Log the SMS for development
            current_app.logger.info(f"SMS NOTIFICATION (not sent - no credentials):")
            current_app.logger.info(f"To: {phone_number}")
            current_app.logger.info(f"Message: {message}")
            return True
        
        try:
            # Truncate message if too long (SMS limit is 160 characters)
            if len(message) > 160:
                message = message[:157] + "..."
            
            # Send SMS
            sms = self.client.messages.create(
                body=message,
                from_=self.phone_number,
                to=phone_number
            )
            
            current_app.logger.info(f"SMS sent successfully to {phone_number}. SID: {sms.sid}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Twilio SMS error: {e}")
            return False
    
    def _clean_phone_number(self, phone_number):
        """Clean and format phone number"""
        # Remove any non-digit characters
        cleaned = ''.join(filter(str.isdigit, phone_number))
        
        # Add country code if not present (assuming Nigeria +234)
        if len(cleaned) == 10 and cleaned.startswith('0'):
            cleaned = '234' + cleaned[1:]  # Replace leading 0 with 234
        elif len(cleaned) == 11 and not cleaned.startswith('234'):
            cleaned = '234' + cleaned
        
        return '+' + cleaned
    
    def send_verification_code(self, phone_number, code):
        """Send verification code via SMS"""
        message = f"Your verification code is: {code}. This code will expire in 10 minutes."
        return self.send_notification_sms(phone_number, message, 'verification')
    
    def send_payment_alert(self, phone_number, amount, status, reference):
        """Send payment status alert"""
        if status == 'success':
            message = f"Payment successful: ₦{amount:,.2f}. Ref: {reference}"
        else:
            message = f"Payment failed: ₦{amount:,.2f}. Ref: {reference}"
        
        return self.send_notification_sms(phone_number, message, 'payment')


class WhatsAppService:
    """Service for sending WhatsApp notifications (placeholder for future implementation)"""
    
    def __init__(self):
        self.api_key = os.environ.get('WHATSAPP_API_KEY')
        self.phone_number = os.environ.get('WHATSAPP_PHONE_NUMBER')
        
        # Use print for initialization without app context
        print("WhatsApp service initialized (placeholder implementation)")
    
    def send_whatsapp_message(self, phone_number, message, category='general'):
        """
        Send WhatsApp message (placeholder implementation)
        
        Args:
            phone_number: Recipient WhatsApp number
            message: Message text
            category: Message category
        """
        
        # Placeholder implementation - log for now
        current_app.logger.info(f"WHATSAPP MESSAGE (placeholder - not sent):")
        current_app.logger.info(f"To: {phone_number}")
        current_app.logger.info(f"Message: {message}")
        current_app.logger.info(f"Category: {category}")
        
        # TODO: Implement actual WhatsApp API integration
        # This could use WhatsApp Business API, Twilio WhatsApp, or other providers
        
        return True
    
    def send_job_match_alert(self, phone_number, job_title, company_name):
        """Send job match alert via WhatsApp"""
        message = f"🔔 New job match: {job_title} at {company_name}. Check the app for details!"
        return self.send_whatsapp_message(phone_number, message, 'job_match')
    
    def send_application_update(self, phone_number, job_title, status):
        """Send application status update via WhatsApp"""
        status_emojis = {
            'accepted': '🎉',
            'rejected': '😔',
            'interview': '📞',
            'withdrawn': '↩️'
        }
        
        emoji = status_emojis.get(status, '📝')
        message = f"{emoji} Application update: Your application for {job_title} is now {status}."
        
        return self.send_whatsapp_message(phone_number, message, 'application')