import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY", "")
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET", "")
TWILIO_FROM = os.getenv("TWILIO_FROM", "")
GUARDIAN_PHONE = os.getenv("GUARDIAN_PHONE", "")

# Email Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
GUARDIAN_EMAIL = os.getenv("GUARDIAN_EMAIL", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# Fall Detection Configuration
FALL_ANGLE_THRESHOLD = float(os.getenv("FALL_ANGLE_THRESHOLD", 60))  # degrees
FALL_TIME_THRESHOLD = float(os.getenv("FALL_TIME_THRESHOLD", 2))    # seconds
COOLDOWN_PERIOD = float(os.getenv("COOLDOWN_PERIOD", 30))           # seconds before sending another alert

# Model Configuration
MODEL_PATH = os.getenv("MODEL_PATH", "yolov8n-pose.pt")
