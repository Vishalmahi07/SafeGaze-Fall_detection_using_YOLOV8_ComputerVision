from twilio.rest import Client
import config
from database.db import log_alert

def send_sms_alert(message: str):
    """
    Sends an SMS alert using the Twilio API.
    """
    if not config.TWILIO_ACCOUNT_SID or not config.TWILIO_AUTH_TOKEN:
        print("[WARN] Twilio credentials not configured. SMS not sent.")
        return False
        
    try:
        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        
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
