import smtplib
from email.message import EmailMessage
import config
import os

def send_email_alert(subject: str, body: str, snapshot_path: str = None):
    """
    Sends an Email alert using SMTP, optionally attaching an image snapshot.
    """
    if not config.EMAIL_SENDER or not config.EMAIL_PASSWORD:
        print("[WARN] Email credentials not configured. Email not sent.")
        return False
        
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = config.EMAIL_SENDER
        msg['To'] = config.GUARDIAN_EMAIL
        msg.set_content(body)

        # Attach snapshot if exists
        if snapshot_path and os.path.exists(snapshot_path):
            with open(snapshot_path, 'rb') as f:
                img_data = f.read()
                msg.add_attachment(img_data, maintype='image',
                                   subtype='jpeg', filename=os.path.basename(snapshot_path))

        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.send_message(msg)

        print("> Email Alert sent successfully!")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send Email: {e}")
        return False
