"""
SafeGaze Chatbot — FAQ + Google Gemini AI hybrid engine.
FAQ keywords are checked first (instant, free).
If no FAQ match, falls back to Gemini AI with live system context.
"""
import os
import re
import asyncio
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_AVAILABLE = False

if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
        print("[Chatbot] ✅ Gemini AI enabled")
    except Exception as e:
        print(f"[Chatbot] ⚠️  Gemini setup failed: {e}")
else:
    print("[Chatbot] ℹ️  No GEMINI_API_KEY found. Running in FAQ-only mode.")

# ─── System Prompt for Gemini ────────────────────────────────────────────────
SYSTEM_PROMPT = """You are SafeGaze Assistant, an intelligent AI helper for the SafeGaze Fall Detection System.

PROJECT OVERVIEW:
SafeGaze is a real-time fall detection system that uses a webcam and AI to detect when someone falls and immediately notifies caregivers/guardians.

TECHNICAL STACK:
- YOLOv8n-Pose model: Detects 17 body keypoints per person
- Fall logic: If body angle from vertical < 60° for 2+ consecutive seconds → fall detected
- Alerts: SMS via Twilio + Email via Gmail SMTP (with snapshot photo attached)
- Database: SQLite for event logging
- Backend: FastAPI (Python) running at localhost:8000
- Frontend: HTML/CSS/JS dashboard with live MJPEG webcam feed
- OpenCV: Reads webcam and annotates frames

CONFIGURATION (from .env):
- FALL_ANGLE_THRESHOLD: 60 degrees
- FALL_TIME_THRESHOLD: 2 seconds
- COOLDOWN_PERIOD: 30 seconds between alerts

GUARDIAN ALERTS:
- SMS sent to registered guardian phone via Twilio
- Email sent to registered guardian email with a snapshot photo of the detected fall

PAGES:
- / → Login page (credentials: set in .env)
- /dashboard → Project overview dashboard
- /monitor → Live webcam feed with detection overlay
- /alerts API → Recent alert history

RESPONSE GUIDELINES:
- Be friendly, helpful and empathetic
- Keep responses concise but complete
- Use markdown formatting: **bold**, `code`, bullet points
- For emergencies, always prioritize calling 112 (India) or local emergency number
- If asked something unrelated to SafeGaze, gently redirect to project topics
- Use emojis sparingly but effectively for readability
- Never reveal full credentials or API keys
"""

# ─── FAQ Database ─────────────────────────────────────────────────────────────
# Each entry: keywords (substrings to scan), response (or None for dynamic), dynamic_key
FAQ_DB = [
    {
        "keywords": ["hello", "hi ", "hey ", "hii", "hai", "namaste", "good morning",
                     "good evening", "good afternoon", "wassup", "sup "],
        "response": (
            "👋 **Hello! Welcome to SafeGaze Assistant!**\n\n"
            "I can help you with:\n"
            "• 🛡️ How the fall detection system works\n"
            "• 🔔 Understanding alerts (SMS & Email)\n"
            "• 🧪 Testing and configuration tips\n"
            "• 🆘 Emergency procedures\n"
            "• 📊 Live system status\n\n"
            "What would you like to know? Or click a quick option below! 👇"
        ),
    },
    {
        "keywords": ["what is safegaze", "about safegaze", "what does it do",
                     "explain safegaze", "what is this system", "purpose of this",
                     "what is this project", "tell me about"],
        "response": (
            "🛡️ **SafeGaze — AI-Powered Fall Detection**\n\n"
            "SafeGaze monitors people in real-time using a webcam and instantly alerts caregivers if a fall occurs.\n\n"
            "**How it works:**\n"
            "1. 📷 Webcam streams video live\n"
            "2. 🤖 YOLOv8 AI identifies 17 body keypoints\n"
            "3. 📐 Body angle is calculated continuously\n"
            "4. ⏱️ If angle < 60° for 2+ seconds → **fall detected**\n"
            "5. 🚨 SMS + Email alert sent to guardian instantly\n\n"
            "**Ideal for:** Elderly care, hospitals, rehabilitation centers."
        ),
    },
    {
        "keywords": ["how does fall detection work", "how does it detect", "how yolo",
                     "how is fall detected", "detection work", "how fall", "angle",
                     "keypoint", "pose estimation", "yolov8"],
        "response": (
            "🦴 **How Fall Detection Works (Step by Step):**\n\n"
            "1. **Webcam** captures video ~30 fps\n"
            "2. **YOLOv8-Pose** identifies 17 body keypoints:\n"
            "   nose, shoulders, elbows, wrists, hips, knees, ankles\n"
            "3. **Angle calculation** between shoulder midpoint and hip midpoint:\n"
            "   • Standing upright ≈ 85–90°\n"
            "   • Bending over ≈ 45–60°\n"
            "   • Fallen / lying down ≈ 0–20°\n"
            "4. **Threshold check:** angle < `60°` sustained for `2 seconds`\n"
            "5. **Alert triggered** → SMS + Email + DB log\n\n"
            "The 2-second buffer prevents false alerts from quick movements like bending down."
        ),
    },
    {
        "keywords": ["alert", "sms", "email", "notification", "who gets notified",
                     "guardian", "twilio", "notify", "message sent"],
        "response": (
            "🔔 **Alert System:**\n\n"
            "When a fall is detected:\n\n"
            "📱 **SMS** (via Twilio)\n"
            "   → Sent to your guardian's phone within seconds\n"
            "   → Message includes timestamp and source\n\n"
            "📧 **Email** (via Gmail SMTP)\n"
            "   → Sent to your guardian's email\n"
            "   → Includes a **snapshot photo** of the detected fall\n\n"
            "💾 **Database log** entry created in SQLite\n\n"
            "⏱️ **Cooldown:** 30 seconds between alerts for the same fall event (prevents spam)."
        ),
    },
    {
        "keywords": ["test alert", "how to test", "test the system", "testing",
                     "trigger alert", "try alert", "send test"],
        "response": (
            "🧪 **Testing the Alert System:**\n\n"
            "Click the **\"Test Alert\"** button available on:\n"
            "• The **Dashboard** → Hero section\n"
            "• The **Live Monitor** → Side panel\n\n"
            "This sends a real SMS + Email alert without needing an actual fall.\n\n"
            "⚠️ There's a **5-second cooldown** between test triggers to prevent spam.\n\n"
            "Check the Recent Alerts panel after testing — a new entry should appear!"
        ),
    },
    {
        "keywords": ["emergency", "fall happened", "someone fell", "what to do if",
                     "actual fall", "real fall", "help someone", "fallen down"],
        "response": (
            "🆘 **Emergency — Someone Has Fallen!**\n\n"
            "**Immediate steps:**\n"
            "1. 📞 **Call 112** (India) or your local emergency number FIRST\n"
            "2. ❌ Don't move the person — check if they're conscious\n"
            "3. 🗣️ Talk to them calmly and keep them warm\n"
            "4. 📧 Check your **Email** — a snapshot was automatically sent\n"
            "5. 📱 Check **SMS** — your guardian was already notified\n\n"
            "**After help arrives:**\n"
            "• View the event in the **Recent Alerts** panel\n"
            "• Review the saved snapshot in the `/snapshots/` folder\n"
            "• SafeGaze cooldown resets after 30 seconds"
        ),
    },
    {
        "keywords": ["status", "is it working", "system status", "currently",
                     "is camera", "camera working", "running", "active"],
        "response": None,
        "dynamic_key": "status",
    },
    {
        "keywords": ["accuracy", "accurate", "false alarm", "false positive",
                     "mistake", "wrong detection", "incorrect", "error rate"],
        "response": (
            "📊 **Detection Accuracy:**\n\n"
            "**Current thresholds** (adjustable in `.env`):\n"
            "• Fall angle: `FALL_ANGLE_THRESHOLD=60` degrees\n"
            "• Sustained duration: `FALL_TIME_THRESHOLD=2` seconds\n\n"
            "**To reduce false alarms:**\n"
            "• Increase `FALL_TIME_THRESHOLD` to 3–4 seconds\n"
            "• Increase `FALL_ANGLE_THRESHOLD` to 50 for stricter detection\n\n"
            "**Known false-positive scenarios:**\n"
            "• Person sitting/sleeping on the floor\n"
            "• Camera angle too low\n"
            "• Poor lighting conditions"
        ),
    },
    {
        "keywords": ["config", "configuration", "settings", "change settings",
                     ".env", "threshold", "customize", "adjust"],
        "response": (
            "⚙️ **Configuration Guide (`.env` file):**\n\n"
            "```\n"
            "FALL_ANGLE_THRESHOLD=60    # Angle below = fall\n"
            "FALL_TIME_THRESHOLD=2      # Seconds to confirm\n"
            "COOLDOWN_PERIOD=30         # Seconds between alerts\n"
            "GUARDIAN_PHONE=+91XXXXXX   # SMS recipient\n"
            "GUARDIAN_EMAIL=xxx@gmail   # Email recipient\n"
            "```\n\n"
            "⚡ **Restart** `python main.py` after any changes for them to take effect."
        ),
    },
    {
        "keywords": ["how to run", "start the system", "launch", "run main",
                     "python main", "how to start", "run the project"],
        "response": (
            "▶️ **How to Run SafeGaze:**\n\n"
            "```\n"
            "cd /path/to/Fall_detection\n"
            "source .venv/bin/activate\n"
            "python main.py\n"
            "```\n\n"
            "Then open your browser: **http://localhost:8000**\n\n"
            "Login → Dashboard → Click **\"Launch Live Monitor\"**"
        ),
    },
    {
        "keywords": ["snapshots", "photo", "image", "screenshot", "snapshot saved",
                     "where is photo", "saved image"],
        "response": (
            "📸 **Fall Snapshots:**\n\n"
            "Every time a fall is detected, a photo is automatically saved:\n\n"
            "📁 Location: `Fall_detection/snapshots/fall_alert_YYYYMMDD_HHMMSS.jpg`\n\n"
            "The same photo is also attached to the **Email alert** sent to your guardian."
        ),
    },
    {
        "keywords": ["database", "logs", "history", "sqlite", "stored", "data saved",
                     "fall history", "past alerts"],
        "response": (
            "💾 **Database & Alert History:**\n\n"
            "All fall events are stored in `fall_detection.db` (SQLite).\n\n"
            "Each record contains:\n"
            "• Timestamp of the fall\n"
            "• Status (FALL DETECTED)\n"
            "• Snapshot path\n\n"
            "View recent alerts in the **Recent Alerts** panel on the dashboard or monitor page.\n"
            "The API `/alerts` returns the last 20 events."
        ),
    },
    {
        "keywords": ["thank", "thanks", "thank you", "great", "perfect",
                     "awesome", "good", "nice", "cool", "wow"],
        "response": (
            "😊 You're welcome! Stay safe with SafeGaze.\n\n"
            "If you have more questions, I'm always here to help! 🛡️"
        ),
    },
    {
        "keywords": ["login", "credentials", "password", "username", "how to login",
                     "can't login", "login issue"],
        "response": (
            "🔐 **Login Credentials:**\n\n"
            "Your login credentials are stored in the `.env` file:\n\n"
            "```\n"
            "LOGIN_USERNAME=admin\n"
            "LOGIN_PASSWORD=SafeGaze@2024\n"
            "```\n\n"
            "You can change them anytime by editing `.env` and restarting the server.\n\n"
            "💡 **Tip:** Credentials are stored as plain text in `.env` —"
            " keep that file private and never commit it to GitHub."
        ),
    },
]


# ─── FAQ Matching Engine ──────────────────────────────────────────────────────
def match_faq(message: str):
    """
    Scores each FAQ entry against the user message using keyword substring matching.
    Returns the best-matching FAQ entry or None.
    """
    message_lower = " " + message.lower().strip() + " "

    best_faq = None
    best_score = 0

    for faq in FAQ_DB:
        score = 0
        for keyword in faq["keywords"]:
            if keyword in message_lower:
                score += len(keyword.split())  # longer phrases = higher weight
        if score > best_score:
            best_score = score
            best_faq = faq

    return best_faq if best_score > 0 else None


# ─── Dynamic Status Response ──────────────────────────────────────────────────
def format_status_response(live_data: dict) -> str:
    status = live_data.get("status", "Unknown")
    alerts_count = live_data.get("alerts_count", 0)
    is_normal = status != "FALL DETECTED"

    if is_normal:
        return (
            "✅ **System Status: NORMAL**\n\n"
            f"• 🤖 **Detection Model:** YOLOv8n-Pose — Active\n"
            f"• 📊 **Total Alerts Logged:** {alerts_count}\n"
            f"• 🔄 **Monitoring:** Running\n"
            f"• 🌐 **Web Interface:** http://localhost:8000\n\n"
            "Everything is running smoothly! 🛡️"
        )
    else:
        return (
            "🚨 **ALERT: FALL DETECTED — System Status: CRITICAL**\n\n"
            "A fall is currently being detected!\n\n"
            "**Immediate actions:**\n"
            "1. 📞 Call 112 (India) immediately\n"
            "2. 📱 Check SMS — guardian has been notified\n"
            "3. 📧 Check Email — snapshot photo was sent\n"
            "4. 👁️ Open the **Live Monitor** to view the feed now\n\n"
            f"📊 Total alerts logged: {alerts_count}"
        )


# ─── Gemini AI Call ───────────────────────────────────────────────────────────
def _call_gemini_sync(message: str, history: list, live_data: dict) -> str:
    """Synchronous Gemini call (run in thread pool)."""
    import google.generativeai as genai

    # Build conversation context string
    history_text = ""
    for msg in history[-6:]:  # Last 3 exchanges for context
        role = "User" if msg.get("role") == "user" else "SafeGaze Assistant"
        history_text += f"{role}: {msg.get('content', '')}\n"

    # Build live data context
    live_context = ""
    if live_data:
        recent = live_data.get("recent_alerts", [])
        recent_str = ", ".join(
            [f"{a.get('timestamp','?')} ({a.get('status','?')})" for a in recent[:3]]
        ) if recent else "None"
        live_context = (
            f"\n\nLIVE SYSTEM DATA (as of this moment):\n"
            f"- Current detection status: {live_data.get('status', 'Unknown')}\n"
            f"- Total alerts in database: {live_data.get('alerts_count', 0)}\n"
            f"- Recent alerts: {recent_str}\n"
        )

    prompt = (
        f"{SYSTEM_PROMPT}"
        f"{live_context}"
        f"\n\nCONVERSATION HISTORY:\n{history_text}"
        f"\nUser: {message}\n"
        f"SafeGaze Assistant:"
    )

    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config=genai.GenerationConfig(
            max_output_tokens=450,
            temperature=0.65,
        ),
    )
    response = model.generate_content(prompt)
    return response.text.strip()


# ─── Main Entry Point ─────────────────────────────────────────────────────────
async def get_chat_response(message: str, history: list, live_data: dict = None) -> dict:
    """
    Main chat handler. Checks FAQ first, then falls back to Gemini AI.
    Returns dict with: response (str), source ('faq' | 'ai' | 'fallback' | 'error')
    """
    if not message or not message.strip():
        return {
            "response": "Please type a message and I'll be happy to help! 😊",
            "source": "faq",
        }

    # 1. Check FAQ
    faq = match_faq(message)

    if faq is not None:
        # Handle dynamic status response
        if faq.get("dynamic_key") == "status":
            return {
                "response": format_status_response(live_data or {}),
                "source": "faq",
            }
        return {"response": faq["response"], "source": "faq"}

    # 2. Fallback: Gemini AI
    if GEMINI_AVAILABLE:
        try:
            response_text = await asyncio.to_thread(
                _call_gemini_sync, message, history, live_data
            )
            return {"response": response_text, "source": "ai"}
        except Exception as e:
            print(f"[Chatbot] Gemini error: {e}")
            return {
                "response": (
                    "⚠️ I had trouble connecting to AI right now. "
                    "Try asking about: fall detection, alerts, configuration, "
                    "emergency steps, or system status."
                ),
                "source": "error",
            }

    # 3. No Gemini — polite fallback
    return {
        "response": (
            "I'm currently running in FAQ mode. I can answer questions about:\n\n"
            "• 🛡️ What SafeGaze is\n"
            "• 🦴 How fall detection works\n"
            "• 🔔 SMS & Email alerts\n"
            "• 🧪 Testing the system\n"
            "• ⚙️ Configuration & settings\n"
            "• 🆘 Emergency procedures\n\n"
            "To enable AI answers for anything, add `GEMINI_API_KEY` to your `.env` file "
            "(free at [aistudio.google.com](https://aistudio.google.com))."
        ),
        "source": "fallback",
    }
