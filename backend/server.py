from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import time
import asyncio
from database.db import get_recent_alerts

app = FastAPI()

# Shared state between the FastAPI thread and OpenCV thread
app.state.latest_frame_bytes = None
app.state.current_status = "NORMAL"

# Keep track of last test alert to avoid spam during manual tests
last_test_alert_time = 0

async def frame_generator():
    """Generates frames for the MJPEG stream."""
    while True:
        if app.state.latest_frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + app.state.latest_frame_bytes + b'\r\n')
        # Add a small delay to control stream FPS and avoid pegging CPU
        await asyncio.sleep(0.05) 

@app.get("/video_feed")
async def video_feed():
    """Route returning the multipart mjpeg stream."""
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/status")
async def get_status():
    """Returns the current detection status."""
    return {"status": app.state.current_status}

@app.get("/alerts")
async def get_recent():
    """Returns last 20 alerts from DB."""
    return get_recent_alerts(limit=20)

@app.post("/test_alert")
async def test_alert():
    """Manually triggers a test alert, ignoring cooldowns but applying a minor test cooldown."""
    global last_test_alert_time
    if time.time() - last_test_alert_time < 5:
        return {"success": False, "message": "Test alert on cooldown"}
        
    # We set a flag or just force the main loop to execute an alert
    app.state.trigger_test_alert = True
    last_test_alert_time = time.time()
    return {"success": True, "message": "Test alert triggered"}

# Serve the static frontend (we put it last so endpoints don't get clouded)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
