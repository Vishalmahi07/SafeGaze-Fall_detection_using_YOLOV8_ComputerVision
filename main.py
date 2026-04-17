import cv2
import threading
import uvicorn
import time
import os
from datetime import datetime

from config import MODEL_PATH
from database.db import init_db, log_alert, SNAPSHOTS_DIR
from model.pose_model import PoseModel
from detection.fall_logic import FallDetector
from alerts.sms_alert import send_sms_alert
from alerts.email_alert import send_email_alert

# Import the FastAPI app instance to share state
from backend.server import app

# ─── OpenCV overlay helpers ───────────────────────────────────────────────────
def _draw_text_bg(frame, text, pos, font_scale=0.55, color=(255,255,255),
                  bg_color=(0,0,0), thickness=1, padding=4):
    """Draws text with a filled background rectangle for readability."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = pos
    cv2.rectangle(frame,
                  (x - padding, y - th - padding),
                  (x + tw + padding, y + baseline + padding),
                  bg_color, cv2.FILLED)
    cv2.putText(frame, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)

def draw_debug_overlay(frame, status, debug_info):
    """
    Draws a semi-transparent HUD on the frame with live detection metrics.
    Helps you visually verify what the algorithm is seeing.
    """
    h, w = frame.shape[:2]

    # ── Status banner ──────────────────────────────────────────────────────────
    if status == "FALL DETECTED":
        banner_color = (0, 0, 200)          # dark red BG
        text_color   = (0, 50, 255)         # bright red text
        label        = "  FALL DETECTED!  "
    else:
        banner_color = (0, 80, 0)
        text_color   = (50, 220, 50)
        label        = "  NORMAL  "

    # Full-width semi-transparent banner
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 44), banner_color, cv2.FILLED)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, label, (12, 30),
                cv2.FONT_HERSHEY_DUPLEX, 0.9, text_color, 2, cv2.LINE_AA)
    cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), (w - 90, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)

    # ── Debug metrics HUD (bottom-left) ───────────────────────────────────────
    if debug_info:
        lines = []
        angle = debug_info.get("torso_angle_deg")
        if angle is not None:
            lines.append(f"Torso angle : {angle:.1f} deg")

        aspect = debug_info.get("aspect_ratio")
        if aspect is not None:
            lines.append(f"Aspect ratio: {aspect:.2f}  {'[WIDE]' if aspect < 0.75 else '[TALL]'}")

        drop = debug_info.get("drop_score")
        if drop is not None:
            lines.append(f"Drop score  : {drop:.2f}")

        fused = debug_info.get("fused_score")
        if fused is not None:
            bar_len = int(fused * 120)
            bar_color = (0, 0, 220) if fused >= 0.48 else (0, 180, 80)
            lines.append(f"Fall score  : {fused:.3f}")
            # Draw mini progress bar
            bar_y = h - 14
            cv2.rectangle(frame, (10, bar_y), (10 + 120, bar_y + 6), (50,50,50), cv2.FILLED)
            cv2.rectangle(frame, (10, bar_y), (10 + bar_len, bar_y + 6), bar_color, cv2.FILLED)
            cv2.putText(frame, "FALL SCORE", (136, bar_y + 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (130,130,130), 1)

        panel_h = len(lines) * 20 + 12
        panel_y_start = h - 20 - panel_h
        overlay2 = frame.copy()
        cv2.rectangle(overlay2, (6, panel_y_start), (230, panel_y_start + panel_h),
                      (10, 10, 10), cv2.FILLED)
        cv2.addWeighted(overlay2, 0.6, frame, 0.4, 0, frame)

        for i, line in enumerate(lines):
            y_pos = panel_y_start + 16 + i * 20
            cv2.putText(frame, line, (12, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)

    # ── Red border flash on fall ───────────────────────────────────────────────
    if status == "FALL DETECTED":
        border = 6
        cv2.rectangle(frame, (border, border), (w - border, h - border),
                      (0, 0, 255), border)


# ─── FastAPI server thread ────────────────────────────────────────────────────
def run_fastapi_server():
    """Runs the FastAPI server in a separate thread."""
    print("[INFO] Starting FastAPI server on http://localhost:8000...")
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    server.run()


# ─── Alert sequence ───────────────────────────────────────────────────────────
def trigger_alert_sequence(frame, source="System"):
    """Handles the full sequence of logging and sending alerts."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = os.path.join(SNAPSHOTS_DIR, f"fall_alert_{timestamp}.jpg")

    cv2.imwrite(snapshot_path, frame)

    log_alert("FALL DETECTED", snapshot_path)
    print(f"[ALERT] Logged Fall Event at {timestamp}")

    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sms_text = (f"ALERT ({source}): Fall detected at {time_str}. "
                f"Please check immediately.")
    email_subject = "Critical Alert: Fall Detected — Immediate Attention Required"
    email_body = (f"A fall was detected by the {source} System at {time_str}.\n\n"
                  f"Please review the attached snapshot.\n")

    send_sms_alert(sms_text)
    send_email_alert(email_subject, email_body, snapshot_path)


# ─── Main loop ────────────────────────────────────────────────────────────────
def main():
    # 1. Initialize SQLite Database
    init_db()

    # 2. Start FastAPI server thread
    server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
    server_thread.start()
    time.sleep(1)

    # 3. Initialize Models and Components
    pose_model   = PoseModel(model_path=MODEL_PATH)
    fall_detector = FallDetector()

    # 4. Start webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    # Boost resolution if available (helps with keypoint accuracy)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("[INFO] Starting Fall Detection Loop. Press 'q' to quit.")
    print("[INFO] Debug HUD is shown on the local OpenCV window.")

    fall_already_handled = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Failed to grab frame. Exiting loop.")
            break

        # ── Manual test alert from frontend ───────────────────────────────────
        if getattr(app.state, 'trigger_test_alert', False):
            print("[INFO] Manually triggering test alert sequence...")
            trigger_alert_sequence(frame, "Manual Test")
            app.state.trigger_test_alert = False

        # ── Pose inference ─────────────────────────────────────────────────────
        results = pose_model.predict(frame)
        annotated_frame = results[0].plot() if len(results) > 0 else frame.copy()
        current_status  = "NORMAL"

        # Process the highest-confidence detected person
        if len(results) > 0 and results[0].keypoints is not None:
            kp_data = results[0].keypoints.data
            if len(kp_data) > 0:
                # Pick the first (highest-confidence) detection
                keypoints      = kp_data[0].cpu().numpy()
                current_status = fall_detector.process_keypoints(keypoints)

        app.state.current_status = current_status

        # ── Alert trigger ──────────────────────────────────────────────────────
        if current_status == "FALL DETECTED":
            if not fall_already_handled:
                trigger_alert_sequence(frame, "AI Vision")
                fall_already_handled = True
        else:
            fall_already_handled = False

        # ── Draw HUD overlay (local window + web stream) ───────────────────────
        draw_debug_overlay(annotated_frame, current_status, fall_detector.debug_info)

        # ── Stream to web dashboard ────────────────────────────────────────────
        ret_enc, buffer = cv2.imencode(
            '.jpg', annotated_frame,
            [cv2.IMWRITE_JPEG_QUALITY, 85]
        )
        if ret_enc:
            app.state.latest_frame_bytes = buffer.tobytes()

        # ── Local display ──────────────────────────────────────────────────────
        cv2.imshow("SafeGaze — Fall Detection", annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
