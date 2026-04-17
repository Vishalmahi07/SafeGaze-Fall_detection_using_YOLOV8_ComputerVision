from twilio.rest import Client
import config
from database.db import log_alert

def send_sms_alert(message: str):
    """
    Sends an SMS alert using the Twilio API.
    """
    if not config.TWILIO_ACCOUNT_SID:
        print("[WARN] Twilio Account SID not configured. SMS not sent.")
        return False
        
    try:
        # Check if using API Key/Secret or standard Auth Token
        if config.TWILIO_API_KEY and config.TWILIO_API_SECRET:
            client = Client(username=config.TWILIO_API_KEY, password=config.TWILIO_API_SECRET, account_sid=config.TWILIO_ACCOUNT_SID)
        elif config.TWILIO_AUTH_TOKEN:
            client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        else:
            print("[WARN] Twilio credentials (Auth Token or API Key/Secret) not configured. SMS not sent.")
            return False
            
        message_obj = client.messages.create(
            body=message,
            from_=config.TWILIO_FROM,
            to=config.GUARDIAN_PHONE
        )
        print(f"> SMS Alert sent successfully via Twilio! SID: {message_obj.sid}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send SMS via Twilio: {e}")
        return False
