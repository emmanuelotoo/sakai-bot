"""
WhatsApp Cloud API client.

Sends notifications via Meta's WhatsApp Cloud API.
https://developers.facebook.com/docs/whatsapp/cloud-api
"""

import logging
from typing import Optional

import requests

from sakai_bot.config import get_settings

logger = logging.getLogger(__name__)

# Meta Graph API endpoint for WhatsApp messages
WHATSAPP_API_URL = "https://graph.facebook.com/v18.0/{phone_number_id}/messages"


class WhatsAppNotifier:
    """
    WhatsApp Cloud API client for sending notifications.
    
    Uses Meta's Cloud API to send text messages to a configured
    recipient phone number.
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        recipient_phone: Optional[str] = None,
    ):
        """
        Initialize WhatsApp notifier.
        
        Args:
            token: WhatsApp Cloud API access token
            phone_number_id: WhatsApp Business phone number ID
            recipient_phone: Recipient phone number (with country code)
        """
        settings = get_settings()
        
        self.token = token or settings.whatsapp_token
        self.phone_number_id = phone_number_id or settings.whatsapp_phone_number_id
        self.recipient_phone = recipient_phone or settings.whatsapp_recipient_phone
        
        self.api_url = WHATSAPP_API_URL.format(phone_number_id=self.phone_number_id)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })
    
    def send_message(self, message: str) -> bool:
        """
        Send a text message via WhatsApp.
        
        Args:
            message: The message text to send
            
        Returns:
            bool: True if message was sent successfully
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.recipient_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message,
            },
        }
        
        try:
            response = self.session.post(self.api_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                message_id = data.get("messages", [{}])[0].get("id", "unknown")
                logger.info(f"WhatsApp message sent successfully: {message_id}")
                return True
            else:
                logger.error(
                    f"WhatsApp API error: {response.status_code} - {response.text}"
                )
                return False
                
        except requests.exceptions.Timeout:
            logger.error("WhatsApp API request timed out")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"WhatsApp API request failed: {e}")
            return False
    
    def send_template_message(
        self,
        template_name: str,
        language_code: str = "en",
        components: Optional[list] = None,
    ) -> bool:
        """
        Send a template message via WhatsApp.
        
        Template messages are pre-approved message formats required
        for initiating conversations outside the 24-hour window.
        
        Args:
            template_name: Name of the approved template
            language_code: Language code for the template
            components: Optional template components (header, body, etc.)
            
        Returns:
            bool: True if message was sent successfully
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.recipient_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        
        if components:
            payload["template"]["components"] = components
        
        try:
            response = self.session.post(self.api_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"WhatsApp template message sent: {template_name}")
                return True
            else:
                logger.error(
                    f"WhatsApp template API error: {response.status_code} - {response.text}"
                )
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"WhatsApp template request failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test WhatsApp API connection by sending a test message.
        
        Returns:
            bool: True if connection is working
        """
        return self.send_message("🤖 Sakai Bot connection test successful!")
