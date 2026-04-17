import os
import time
import asyncio
from functools import wraps

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import (
    StreamingResponse, HTMLResponse, RedirectResponse, JSONResponse
)
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel
from dotenv import load_dotenv
from database.db import get_recent_alerts
from backend.chatbot import get_chat_response

load_dotenv()

# ─── Config ────────────────────────────────────────────────────────────────────
LOGIN_USERNAME = os.getenv("LOGIN_USERNAME", "admin")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "SafeGaze@2024")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
COOKIE_NAME = "safegaze_session"
SESSION_MAX_AGE = 60 * 60 * 8  # 8 hours

serializer = URLSafeTimedSerializer(SECRET_KEY)

# ─── App ────────────────────────────────────────────────────────────────────────
app = FastAPI()

# Shared state between FastAPI thread and OpenCV thread
app.state.latest_frame_bytes = None
app.state.current_status = "NORMAL"
app.state.trigger_test_alert = False

# Keep track of last test alert to avoid spam
last_test_alert_time = 0

# ─── Auth helpers ───────────────────────────────────────────────────────────────
def create_session_cookie(username: str) -> str:
    return serializer.dumps(username)

def verify_session_cookie(token: str):
    """Returns username or None."""
    try:
        username = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return username
    except (BadSignature, SignatureExpired):
        return None

def get_current_user(request: Request):
    """Returns username if authenticated, else None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return verify_session_cookie(token)

def require_auth(request: Request):
    """Dependency that raises redirect if not authenticated."""
    user = get_current_user(request)
    if not user:
        # Raise a redirect response
        raise RedirectResponseException(url="/")
    return user

class RedirectResponseException(Exception):
    def __init__(self, url: str, status_code: int = 302):
        self.url = url
        self.status_code = status_code

# ─── MJPEG Stream ───────────────────────────────────────────────────────────────
async def frame_generator():
    """Generates frames for the MJPEG stream."""
    while True:
        if app.state.latest_frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + app.state.latest_frame_bytes + b'\r\n')
        await asyncio.sleep(0.05)

# ─── Exception handler ──────────────────────────────────────────────────────────
@app.exception_handler(RedirectResponseException)
async def redirect_exception_handler(request: Request, exc: RedirectResponseException):
    return RedirectResponse(url=exc.url, status_code=exc.status_code)

# ─── Auth Routes ────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve login page; redirect to dashboard if already logged in."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    with open("frontend/login.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
        token = create_session_cookie(username)
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            max_age=SESSION_MAX_AGE,
            samesite="lax",
        )
        return response
    # Bad credentials — redirect back with error flag
    return RedirectResponse(url="/?error=1", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return RedirectResponse(url="/")

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response

# ─── Protected Pages ────────────────────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(user: str = Depends(require_auth)):
    with open("frontend/dashboard.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/monitor", response_class=HTMLResponse)
async def monitor(user: str = Depends(require_auth)):
    with open("frontend/monitor.html", "r") as f:
        return HTMLResponse(content=f.read())

# ─── Protected API Endpoints ────────────────────────────────────────────────────
@app.get("/video_feed")
async def video_feed(user: str = Depends(require_auth)):
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/status")
async def get_status(user: str = Depends(require_auth)):
    return {"status": app.state.current_status}

@app.get("/alerts")
async def get_recent(user: str = Depends(require_auth)):
    return get_recent_alerts(limit=20)

@app.post("/test_alert")
async def test_alert(user: str = Depends(require_auth)):
    global last_test_alert_time
    if time.time() - last_test_alert_time < 5:
        return {"success": False, "message": "Test alert on cooldown"}
    app.state.trigger_test_alert = True
    last_test_alert_time = time.time()
    return {"success": True, "message": "Test alert triggered"}


# ─── Chat Endpoint ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list = []


@app.post("/chat")
async def chat(req: ChatRequest, user: str = Depends(require_auth)):
    """Hybrid chatbot: FAQ first, Gemini AI fallback, with live system data."""
    # Gather live context
    all_alerts = get_recent_alerts(limit=50)
    live_data = {
        "status": app.state.current_status,
        "alerts_count": len(all_alerts),
        "recent_alerts": all_alerts[:3],
    }
    result = await get_chat_response(req.message, req.history, live_data)
    return result

# ─── Static files (CSS/JS/images — accessible without auth) ─────────────────────
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
